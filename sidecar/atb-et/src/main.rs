use anyhow::Result;
use async_nats::jetstream;
use futures_util::StreamExt;
use std::pin::Pin;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::net::UnixListener;
use tokio_stream::wrappers::{ReceiverStream, UnixListenerStream};
use tonic::{transport::Server, Request, Response, Status};

pub mod transport {
    tonic::include_proto!("atr.transport.v1");
}

use transport::atr_transport_server::{AtrTransport, AtrTransportServer};
use transport::{
    EnvelopeFrame, HealthRequest, HealthResponse, PublishRequest, PublishResponse, RequestReplyRequest,
    RequestReplyResponse, SubscribeRequest,
};

type SubscribeStream = Pin<Box<dyn tokio_stream::Stream<Item = Result<EnvelopeFrame, Status>> + Send>>;

#[derive(Clone)]
struct Sidecar {
    nats: async_nats::Client,
    js: jetstream::Context,
}

#[tonic::async_trait]
impl AtrTransport for Sidecar {
    async fn publish(&self, request: Request<PublishRequest>) -> Result<Response<PublishResponse>, Status> {
        let req = request.into_inner();
        let ack = self
            .js
            .publish(req.subject.clone(), req.canonical_envelope.into())
            .await
            .map_err(|e| Status::unavailable(format!("publish failed: {e}")))?
            .await
            .map_err(|e| Status::unavailable(format!("ack failed: {e}")))?;

        Ok(Response::new(PublishResponse {
            accepted: true,
            persisted: true,
            stream_sequence: ack.sequence,
            consumer_sequence: 0,
            subject: req.subject,
            server_time_unix_ns: now_ns(),
            error_code: String::new(),
            error_message: String::new(),
        }))
    }

    type SubscribeStream = SubscribeStream;

    async fn subscribe(&self, request: Request<SubscribeRequest>) -> Result<Response<Self::SubscribeStream>, Status> {
        let req = request.into_inner();
        let mut sub = self
            .nats
            .subscribe(req.subject_filter)
            .await
            .map_err(|e| Status::unavailable(format!("subscribe failed: {e}")))?;
        let (tx, rx) = tokio::sync::mpsc::channel(64);
        tokio::spawn(async move {
            while let Some(msg) = sub.next().await {
                let _ = tx
                    .send(Ok(EnvelopeFrame {
                        canonical_envelope: msg.payload.to_vec(),
                        subject: msg.subject.to_string(),
                        stream_sequence: 0,
                        broker_time_unix_ns: now_ns(),
                    }))
                    .await;
            }
        });

        Ok(Response::new(Box::pin(ReceiverStream::new(rx))))
    }

    async fn health(&self, _request: Request<HealthRequest>) -> Result<Response<HealthResponse>, Status> {
        Ok(Response::new(HealthResponse {
            ok: true,
            nats_connected: true,
            jetstream_ready: true,
            overloaded: false,
            publish_rate_msg_s: 0,
            subscribe_rate_msg_s: 0,
            backlog_msgs: 0,
            version: env!("CARGO_PKG_VERSION").to_string(),
        }))
    }

    async fn request_reply(
        &self,
        request: Request<RequestReplyRequest>,
    ) -> Result<Response<RequestReplyResponse>, Status> {
        let req = request.into_inner();
        let reply = self
            .nats
            .request(req.subject, req.payload.into())
            .await
            .map_err(|e| Status::unavailable(format!("request-reply failed: {e}")))?;

        Ok(Response::new(RequestReplyResponse {
            ok: true,
            payload: reply.payload.to_vec(),
            error_code: String::new(),
            error_message: String::new(),
        }))
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    let socket_path = "/tmp/atb_et.sock";
    let _ = std::fs::remove_file(socket_path);

    let nats = async_nats::connect("nats://127.0.0.1:4222").await?;
    let js = jetstream::new(nats.clone());
    let svc = Sidecar { nats, js };

    let uds = UnixListener::bind(socket_path)?;
    Server::builder()
        .add_service(AtrTransportServer::new(svc))
        .serve_with_incoming(UnixListenerStream::new(uds))
        .await?;
    Ok(())
}

fn now_ns() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos() as i64)
        .unwrap_or(0)
}
