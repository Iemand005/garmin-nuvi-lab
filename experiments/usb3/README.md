# USB3 control completion fix and request tracing

> Historical lab-stage notes. See the [current development guide](../../docs/development.md) for the working player and local setup.

USB2 photo IMG_5012:CFG0101,DEV0007,IRQ008F,REQ0010,OTG000D, orange. These show16host SETUPs and addressed state, not completed enumeration. Original photo/hash and observation saved in evidence/usb2-photo. No successful vendor roundtrip yet.

TI OMAP5912 USB guide SPRU761A Table35/page74 requires clearing endpoint interrupt flags before FIFO enable and disallows enablingEP0 outsidecontroltransfers. This is a related OMAP controller manual, cross-checked against matching stock registers/Linux handler, not actualchipmark identification. Linux ep0_irq clears completion flags before FIFO work and prioritizes newSETUP. Our old handler violated ordering and rearmedOUT even aftercompletedstatus. Synthetic regression againstactualUSB2 bytes reproduces enable-before-ack failure, analysis/usb/usb2-ordering-regression.json; physical rootcause remains to be confirmed.

USB3 retains USB2 initialization/session/guards, fixescompletion ordering, checksTX ACK/STALL, armsOUT only afterINdata completion, leavesOUT unarmed afterstatus, and supersedes stale completions withnewSETUP. NewSETUP arrivingduringread defersoldresponse to nextpoll. No additionalMMIOaddresses, clocks, reset, PHY, DMA or flash/filesystem operations. Samevendorprotocol/hosttool.

Screenleft:DEV(device state),CMD(bRequest<<8|bmRequestType),VAL(wValue),IDX(wIndex),LEN(wLength). CenterTX=lastqueuedreplylength;REQ=servicedSETUPcount, bothhex. Large decimalcounter andbuttonsretained. TitleNUVI/USB3. Photo ofthesevalueswillpinpointlastrequest ifMacstillcannotenumerate. USBbarcolorsunchanged.

Candidate173360bytes SHA59776c8609c5158be51172cfbf7b0d27fe410a77d6a1af0dda99483c16037093. Buildmake_usb3_probe.py thenbuild_rectangle_probe.py --experiment usb3. Audit audit_usb3_probe.py:15UI/hardwarecases,79pairs/buffer,handoff,32protocolcases,4UDC/OTGguards,7completion/SETUPracechecks. Wholeframe/storeconstraints/ABI checked. Syntheticmodel doesnotemulateUSBsignalling/clocks/timing. Physical USB3pending.

stage_usb3_probe.py pinsknownMacSD/UUID/priorUSB2hash, read-onlybydefault, approvedcontinuedtest --install verifiesatomic/fsync/readback thennormaleject. No internalGarminwrites. UserreturnSDfromGarminwhilehostvolumesunmounted; preservepower. Aftercopy/eject,startknownsequencecenter/unlockedandUSBconnected. Capturephotoofreadouts; agentchecksMacstatus, sends321onlyafterlabidentity/protocolmagicverified. RemoveSDbeforerecoveryRESET; neverresetwhilehoststorage mounted.
