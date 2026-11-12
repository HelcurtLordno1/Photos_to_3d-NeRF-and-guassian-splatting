@{
    SchemaVersion = 'single-winner-campaign-1'
    Study = 'final-quality-v1'
    ConfirmationStudy = 'tea-quality-v5'
    ReferenceStudy = 'tea-research-v4'
    Scenes = @('bonsai','room','garden','poster')
    GaussianBudgets = @{ bonsai=1000000; room=1000000; garden=1200000; poster=0 }
    ValidationBudgets = @(300000,450000)
    ValidationSeed = 42
    ValidationViews = 15
    MinimumRoiLpipsGain = 0.05
    MaximumValidationPsnrLoss = 0.2
    MaximumQualityPlyMiB = 110
    MeanParityTargetDb = 35
    MinimumViewParityDb = 30
    MaximumQualityBrowserP95Ms = 33.3
    MinimumTransferParityMeanDb = 25
    MinimumTransferParityViewDb = 20
    MaximumCampaignSeconds = 172800
    MinimumFreeGiB = 70
    HighResolutionLongEdges = @(3840,7680)
    HighResolutionViews4k = 3
    HighResolutionViews8k = 1
}
