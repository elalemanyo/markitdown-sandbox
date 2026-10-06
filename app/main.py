"""Container entrypoint: `serve` starts the web UI, anything else runs the MarkItDown CLI."""

import sys

if len(sys.argv) > 1 and sys.argv[1] == "serve":
    from server import serve

    serve()
else:
    from markitdown.__main__ import main

    sys.argv[0] = "markitdown"
    main()
