import os
import sys
import logging

PACKAGE_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, PACKAGE_PARENT)

from accessbridge.core.state import state_manager
from accessbridge.input.handler import start_input_listeners
from accessbridge.ui.dashboard import Dashboard
from accessbridge.core.utils import set_gui_root

logger = logging.getLogger(__name__) 


def main():
    try: 
        logger.info("AccessBridge startup sequence initiated.")
        print("🟢 AccessBridge Adaptive HUD Initializing...")

        state_manager.load_config()  
        state_manager.load_session()
        start_input_listeners()
 
        dashboard = Dashboard(state_manager)
        root = dashboard.build()
        set_gui_root(root)
 
        print("🖥️  Launching Dashboard GUI Window...")
        dashboard.run()

    except KeyboardInterrupt:
        print("\n🛑 Shutting down gracefully via user interruption request.")
        state_manager.stop_recording()
    except Exception:
        logger.exception("Fatal error occ urred in main execution lifecycle loop")
        state_manager.stop_recording()


if __name__ == "__main__":
    main()
