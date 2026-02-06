#!/usr/bin/env python3

# ~/Library/Application\ Support/iTerm2/Scripts/AutoLaunch に置く

import iterm2
import asyncio
import os
import random

IMAGE_DIR = os.path.expanduser("~/Downloads/background")
INTERVAL_SEC = 20
SUPPORTED_EXT = ('.png', '.jpg', '.jpeg')

def get_images():
    return [
        os.path.join(IMAGE_DIR, f)
        for f in os.listdir(IMAGE_DIR)
        if f.lower().endswith(SUPPORTED_EXT)
    ]

async def apply_background_to_all_sessions(connection, image_path):
    app = await iterm2.async_get_app(connection)

    for window in app.windows:
        for tab in window.tabs:
            for session in tab.sessions:
                profile = await session.async_get_profile()
                await profile.async_set_background_image_location(image_path)

async def main(connection):
    images = get_images()
    if not images:
        raise RuntimeError("Could not Find Background Images.")
    
    print(images)
    index = 0

    while True:
        image = images[index % len(images)]
        index += 1

        await apply_background_to_all_sessions(connection, image)
        await asyncio.sleep(INTERVAL_SEC)

iterm2.run_forever(main)