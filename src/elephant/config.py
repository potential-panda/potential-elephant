import os

DATA_DIR = os.environ.get("ELEPHANT_DATA_DIR", "/panda-infra/elephant")
TICKERS_FILE = os.path.join(DATA_DIR, "tickers.txt")
TICKERS_US_FILE = os.path.join(DATA_DIR, "tickers-us.txt")
SOURCE_REGISTRY_FILE = os.path.join(DATA_DIR, "source_registry.json")
ATLAS_PATH = os.path.join(DATA_DIR, "atlas.json")
DECISIONS_FILE = os.path.join(DATA_DIR, "decisions.json")
