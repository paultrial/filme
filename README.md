# Filme for Kodi

Filme is a static movie-picker web app for Kodi on OSMC. Choosing a title sends it to the local `server.py`, which asks Kodi to play the matching library item.

## Build and run on OSMC

```bash
npm ci
npm run build
python3 server.py
```

`npm run build` creates a fully static `out/` directory. Copy the project (including `out/`, `server.py`, and `public/filme.txt`) to the Pi, then start the Python server. Open `http://<pi-address>:3000` from a device on the same network.

The build reads `public/filme.txt`; it must contain one Kodi filename per line. The original filename is sent to Kodi unchanged so it can be matched against the library.

Kodi's web server and JSON-RPC must be enabled. Configure the Python server as needed:

```bash
KODI_USER=osmc KODI_PASS=your-password MOVIES_DIR=/media/usb/Movies python3 server.py
```

`MOVIES_DIR` is only needed when a movie is absent from Kodi's library. See the comments at the top of `server.py` for all available options.

## Development

Run `npm run dev` while editing. Kodi playback requires `python3 server.py`, since the Next development server does not provide `/api/play`.
