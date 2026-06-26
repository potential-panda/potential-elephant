import os

DATA_DIR = os.environ.get("ELEPHANT_DATA_DIR", "/panda-infra/elephant")
TICKERS_FILE = os.path.join(DATA_DIR, "tickers.txt")
TICKERS_US_FILE = os.path.join(DATA_DIR, "tickers-us.txt")
TREE_PATH = os.path.join(DATA_DIR, "river_tree.json")
DECISIONS_FILE = os.path.join(DATA_DIR, "decisions.json")
