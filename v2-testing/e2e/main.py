"""Entry point for the v2 e2e suite. Runs inside the backend container.

    python /tmp/v2e/main.py [case-name-filter]

Import order is run order — `case_flows` is last so its `flows-sweep` case, which
asserts no ZZE scratch row survived, closes the run.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _suite                                       # noqa: E402
import case_smoke                                   # noqa: E402,F401
import case_theme                                   # noqa: E402,F401
import case_cron                                    # noqa: E402,F401
import case_welcome                                 # noqa: E402,F401
import case_persona_import                          # noqa: E402,F401
import case_feed_collapse                           # noqa: E402,F401
import case_modals                                  # noqa: E402,F401
import case_flows                                   # noqa: E402,F401

if __name__ == '__main__':
    sys.exit(_suite.main())
