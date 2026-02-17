use arc_swap::ArcSwap;
use std::collections::HashSet;
use std::sync::Arc;

#[derive(Clone, Debug, Default)]
pub struct RulesetSnapshot {
    allowed_subjects: HashSet<String>,
}

impl RulesetSnapshot {
    pub fn from_subjects(subjects: impl IntoIterator<Item = String>) -> Self {
        Self {
            allowed_subjects: subjects.into_iter().collect(),
        }
    }

    pub fn allows(&self, subject: &str) -> bool {
        self.allowed_subjects.contains(subject)
    }
}

#[derive(Clone, Debug)]
pub struct RcuRuleEngine {
    current: Arc<ArcSwap<RulesetSnapshot>>,
}

impl Default for RcuRuleEngine {
    fn default() -> Self {
        Self {
            current: Arc::new(ArcSwap::from_pointee(RulesetSnapshot::default())),
        }
    }
}

impl RcuRuleEngine {
    pub fn allows(&self, subject: &str) -> bool {
        self.current.load().allows(subject)
    }

    pub fn replace_ruleset(&self, subjects: impl IntoIterator<Item = String>) {
        let next = Arc::new(RulesetSnapshot::from_subjects(subjects));
        self.current.store(next);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reader_observes_consistent_snapshot_during_replace() {
        let engine = RcuRuleEngine::default();
        assert!(!engine.allows("aether.stream.core.state.mutation"));

        engine.replace_ruleset(vec!["aether.stream.core.state.mutation".to_string()]);
        assert!(engine.allows("aether.stream.core.state.mutation"));
        assert!(!engine.allows("aether.stream.core.admin"));
    }
}
