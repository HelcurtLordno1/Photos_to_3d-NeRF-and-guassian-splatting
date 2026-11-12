@{
    # New experimental profile; the registry and source pins of old runs stay exact.
    Study = 'tea-quality-v2'
    Scene = 'custom:tea_sets_2'
    Condition = 'custom:tea_sets_2-native-v2'
    Method = 'splatfacto'
    Protocol = 'capture-native-30k-v2'
    DownscaleFactor = 1
    Iterations = 30000
    Seed = 42
    MaximumExplorationGpuSeconds = 21600
    TrainPeakMemoryTargetMiB = 12288
    Q2Backend = 'official-improved-gs'
    Q2Status = 'gated-after-q1'
}
