import sys
sys.path.insert(0, './src')

from witness_forge.config import ConfigManager
from witness_forge.forge.loader import ForgeLoader

mgr = ConfigManager('./config.yaml')
cfg = mgr.config
print(f"n_ctx before load: {cfg.model.n_ctx}")

tok, mdl, gen = ForgeLoader.load_model(cfg.model)
print(f"n_ctx after load: {cfg.model.n_ctx}")
