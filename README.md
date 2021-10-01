# isfdb

A tiny tentative framework for interacting with [isfdb.org](http://isfdb.org)
via their [Web API](http://www.isfdb.org/wiki/index.php/Web_API).

Also allows for querying some pages not available via the API but accessible
only to logged in users, e.g. cleanup reports.

## To use
Copy `.credentials_template.json` to `.credentials.json` and add your
credentials.

Look at `add_librisxl_id.py` for an example script.

It is recommended to initialise a `IsfdbSession` instance within a context
manager to avoid having unterminated headless webdriver instances afterwards.
