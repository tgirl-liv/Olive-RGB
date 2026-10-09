"""Standalone mock Qt preview. Does not import the production application."""
from studio_qt.app import main

if __name__ == '__main__':
    raise SystemExit(main())
