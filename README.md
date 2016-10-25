# Link Checker

Follows internal links of a website and checks if they return successful status code.

## Usage

```sh
$ python app.py http://localhost
OK[200] http://localhost
OK[200] http://localhost/about
BAD[404] http://localhost/abuot
```

## Installation

Requires Python >= 3.3, libxml2 and libxslt.

```sh
$ pip install -r requirements.txt
```
