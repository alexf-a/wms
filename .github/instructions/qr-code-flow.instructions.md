---
applyTo: "core/models.py,core/views.py,core/utils.py,core/urls.py"
description: "Instructions for QR Code user flow"
---

Each Unit object has a unique QR code. Users will be able to download and print a Unit's QR code, and paste it on their physical unit. This way, they can scan the Unit's QR code with their phone and be immediately directed to the Unit's detail view.

The QR Code flow is as follows:
1) User scans the physical unit's QR code.
2) WMS app launches.
3) The user is asked to authenticate.
4) If step 3 is successful, the user is brought to the Unit's detail view.