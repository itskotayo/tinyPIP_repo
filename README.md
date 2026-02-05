# tinyPIP_repo
A repository for anything to do with the diy smart watch tinyPIP, made by itskotayo, and inspired by the Fallout francize. 

TinyPIP OS is a custom‑built, ultra‑lightweight wrist‑computer operating system designed specifically for the Raspberry Pi Pico 2 W paired with the Waveshare Pico‑LCD‑1.3 (240×240 IPS) display. It transforms a microcontroller into a responsive, animated, and fully interactive wearable interface—complete with a retro‑inspired UI, joystick navigation, hardware‑level button input, and a modular app architecture.

This isn’t a novelty script. It’s a purpose‑built micro‑OS engineered for clarity, speed, and expandability on constrained hardware.
A Purpose‑Built OS for a Tiny Powerhouse
At the core of TinyPIP OS is the Raspberry Pi Pico 2 W, a dual‑core RP2350 microcontroller with built‑in Wi‑Fi, generous RAM for a microcontroller class device, and a flexible GPIO layout. TinyPIP OS takes full advantage of this hardware:
Hardware Highlights
• 	RP2350 dual‑core MCU for smooth UI updates and background tasks
• 	Wi‑Fi support enabling future OTA updates, dashboards, and network‑aware apps
• 	240×240 IPS LCD with crisp color rendering and fast refresh
• 	5‑way joystick + side buttons mapped to a clean input layer
• 	Low‑power design optimized for wearable use
The OS is architected to feel like a real wrist computer—fast boot, clean transitions, and a UI that feels intentional rather than improvised.

A Clean, Retro‑Modern Interface
TinyPIP OS embraces a terminal‑inspired aesthetic blended with modern micro‑UI design. You get:
• 	A boot animation that gives the OS personality
• 	A home dashboard with system stats and quick‑launch tiles
• 	Monospaced, high‑contrast UI elements for readability
• 	Smooth screen wipes and redraw logic optimized for the Pico’s speed
• 	A layout that respects the 240×240 square display without clutter
It’s nostalgic without being gimmicky—more “micro‑PIP‑Boy” than “Arduino demo”.

A Modular, Extensible Codebase
The OS is written in MicroPython, structured around a modular architecture that makes it easy to add apps, menus, and animations without rewriting the core.
Core System Components
• 	Display driver layer optimized for the Waveshare LCD
• 	Input manager that normalizes joystick + button events
• 	App loader that treats each screen as a module
• 	UI primitives (windows, text blocks, progress bars, icons)
• 	Event loop that keeps the interface responsive
The code is clean, readable, and intentionally structured so you can drop in new features—weather screens, mini‑games, sensors, dashboards—without touching the kernel.

Fast, Expressive, and Fun to Use
TinyPIP OS isn’t just functional—it’s expressive. The boot sequence, the animated avatar, the retro UI, the tactile joystick navigation… it all comes together to make the device feel alive.
You’re not just running a script on a microcontroller.
You’re wearing a tiny, custom‑built operating system that you engineered from the ground up.
