# ATR Subject Taxonomy (NATS / JetStream)

## Planes

### Ingress Plane (raw / pre-immune; optional)
- aether.ingress.<agent_id>.<type>
Retention: WorkQueue (delete on ack)
Storage: File (SSD)

### Stream Plane (verified / canonical)
- aether.stream.<domain>.<event>
Retention: Limits (Age 30d / Size 1TB)
Storage: File (NVMe)

### State Plane (state change notifications)
- aether.state.<entity_id>
Retention: LastValue
Storage: Memory (RAM)

### System Plane (telemetry/heartbeat)
- aether.sys.<node_id>.<metric>
Retention: Age 24h
Storage: Memory (RAM)

### Audit Plane (quarantine)
- aether.audit.violation
Retention: Age 90d
Storage: File (cold tier)

## Sharding / Partitioning (deterministic)
If needed, producers compute shard:
- aether.stream.order.p0.>
- ...
- aether.stream.order.p9.>

Rule:
shard = hash(partition_key or subject) % 10
Publish to aether.stream.order.p{shard}.<event>
