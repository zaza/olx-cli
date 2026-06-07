# olx-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CLI tool for searching and scraping offers from [OLX.pl](https://www.olx.pl), the Polish classifieds marketplace. Built with Python, Click, requests, and BeautifulSoup.

```sh
./olx-cli search rower -l krakow -r 10 -p -m 100 -M 5000 --max-pages 2
```

Python port of [olx-rss](https://github.com/zaza/olx-rss/).