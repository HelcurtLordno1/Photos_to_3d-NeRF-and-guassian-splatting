@{
    SchemaVersion = 'teacher-room-ablation-1'
    Study = 'teacher-room-v1'
    Scene = 'room'
    Arms = @('A','B','C')
    Iterations = 30000
    Seed = 42
    DownscaleFactor = 2
    TrainViews = 272
    EvalViews = 39
    MaximumArmSeconds = 10800
    MinimumFreeGiB = 30
    ContinueFinalCampaign = $true
    FinalStudy = 'final-quality-v1'
}
