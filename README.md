# AudioSocket Framework
This is a python tornado WebSocket server that can receive audio streams for speech recognition or other use-cases.

## [NOTE: THIS PROJECT IS UNDER CONSTRUCTION]  


## Features
* Websocket server that can receive audio streams
* Compatible to SEPIA Framework client speech recognition
* Compatible to Zamia Kalid ASR tools
* Provides a function to playback audio to a caller by CLI
* Provides a handler to print events to the console

## Installation

You'll need Python 2.7 and some dependencies via pip. You may also need header files for Python and OpenSSL,
depending on your operating system. The instructions below are for Ubuntu 14.04.

```bash
sudo apt-get install -y python-pip python-dev libssl-dev
pip install --upgrade virtualenv
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration
The application reads its configuration from an app.conf file in the root directory.

### Port
Default port is given in app.conf file. You can use `ngrok http 20741` to tunnel to your Audiosocket service.

### Path
This is where the framework application will store audio files it records, default is "./recordings/".

## Running
Now you can start the audiosocket service with:

```bash
./venv/bin/python server.py
```
or simply
```bash
python receiver.py
```

If you want to see more verbose logging messsages add a `-v` flag to the startup to see all DEBUG level messages