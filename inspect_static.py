import os
import pathlib
from django.conf import settings

root = pathlib.Path(settings.STATIC_ROOT)
print('static root', root)
for p in ['Images', 'images']:
    d = root / p
    print(p, d.exists(), d.is_dir())
    if d.exists():
        print(sorted([x for x in os.listdir(d) if x.endswith(('.jpg', '.jpeg', '.webp', '.avif', '.png'))])[:20])
