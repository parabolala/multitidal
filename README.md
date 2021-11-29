# Multitidal

Multitidal is a web wrapper for Tidalcycles live coding environment.

Launch the server once and live-code from any device with a web browser.

# What's inside

Multitidal runs a python web-server that drives docker containers. An individual Tidal  `playground` consists of:

 * [supertidebox](https://github.com/efairbanks/supertidebox) container running Tidal, Emacs, SSHd and audio streaming server
 * [WebSSH2](https://github.com/billchurch/webssh2) container exposing Emacs in an SSH session.

# Launching

Set up a python virtual environment:

    $ mkvirtualenv multitidal

Install multitidal code:

    $ pip install -e .

(Optional) Prefetch docker images. Otherwise they'll be downloaded when the first session starts. Might take a few minutes:

    $ docker pull parabolala/supertidebox:1
    $ docker pull parabolala/webssh2:1

Run the server

    $ python multitidal/server.py

Open http://localhost:3000/ in your browser.
