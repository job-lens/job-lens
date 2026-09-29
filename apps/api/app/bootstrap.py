from app.infrastructure import models as infrastructure_models
from app.infrastructure.db import Base
from app.modules.cases import models as case_models
from app.modules.identity import models as identity_models
from app.modules.sop import models as sop_models
from app.modules.support import models as support_models
from app.modules.training import models as training_models

# The composition root is the only place that imports all module models.
MODEL_MODULES = (
    infrastructure_models,
    identity_models,
    case_models,
    sop_models,
    training_models,
    support_models,
)
metadata = Base.metadata
