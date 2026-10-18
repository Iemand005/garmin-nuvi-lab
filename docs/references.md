# References and provenance

Primary references were checked against the copied firmware and then against physical experiments. Related OMAP5912 documentation is a register-layout reference, not proof of the exact SoC marking in either device.

- [TI OMAP5912 display interface, SPRU764B](https://www.ti.com/lit/ug/spru764b/spru764b.pdf)
- [TI OMAP5912 USB controller, SPRU761A](https://www.ti.com/lit/ug/spru761a/spru761a.pdf)
- [TI OMAP5912 serial interfaces, SPRU760C](https://www.ti.com/lit/ug/spru760c/spru760c.pdf), SPI tables 8–13
- [TI OMAP5912 general-purpose interface, SPRU767A](https://www.ti.com/lit/ug/spru767a/spru767a.pdf), GPIO tables 8–10
- [TI TSC2046 datasheet](https://www.ti.com/lit/ds/symlink/tsc2046.pdf), serial timing, control byte, power-down/PENIRQ table
- [Linux OMAP UDC register definitions](https://github.com/torvalds/linux/blob/master/drivers/usb/gadget/udc/omap_udc.h)
- [Linux OMAP UDC implementation](https://github.com/torvalds/linux/blob/master/drivers/usb/gadget/udc/omap_udc.c)
- [Linux OMAP1 USB definitions](https://github.com/torvalds/linux/blob/master/include/linux/soc/ti/omap1-usb.h)
- [Garmin nüvi 350 owner's manual](https://static.garmin.com/pumac/Nuvi350_OwnersManual.pdf)
- [Garmin nüvi 350 quick reference](https://static.garmin.com/pumac/Nuvi350_QuickReferenceGuide.pdf)

The community thread [Running programs from SD on nüvi](https://www.gpspower.net/garmin-receivers-firmwares/236873-running-programs-sd-nuvi.html) supplied an early lead about the SD loader mechanism, including the 350 family. It was not treated as proof that an unmodified 200 binary would work on a 350.

Downloaded PDFs, third-party source reference copies, Garmin firmware/maps, photographs/videos, and raw device XML are intentionally not redistributed here. The repository contains our lab sources and generated diagnostic graphics. macOS fonts are used locally for rendering; font files are not included. Spotify and Garmin are trademarks of their owners; this is an independent experiment.
