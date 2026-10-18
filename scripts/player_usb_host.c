#include <ctype.h>
/* Native IOKit JSON-line RPC for temporary music firmware; no cloud credentials. */
#define main usb_lab_legacy_main
#include "usb_lab_host.c"
#undef main

static int control(IOUSBDeviceInterface197 **dev,unsigned type,unsigned request,
                   unsigned value,unsigned index,unsigned char *reply,unsigned length) {
    IOUSBDevRequestTO req={0};
    req.bmRequestType=(UInt8)type;req.bRequest=(UInt8)request;
    req.wValue=(UInt16)value;req.wIndex=(UInt16)index;
    req.wLength=(UInt16)length;req.pData=reply;
    req.noDataTimeout=1000;req.completionTimeout=2000;
    IOReturn rc=(*dev)->DeviceRequestTO(dev,&req);
    if (rc!=kIOReturnSuccess || req.wLenDone!=length) {
        fprintf(stderr,"Music control0x%x failed0x%08x (%u/%u bytes)\n",request,rc,(unsigned)req.wLenDone,length);
        return 1;
    }
    return 0;
}

int main(int argc,char **argv) {
    if (argc==2 && strcmp(argv[1],"--help")==0) {
        puts("player-usb-host serve\nJSON-line replies; commands:event,ack SEQ,text INDEX WORD,status,quit. Requires music firmware capability.");
        return 0;
    }
    if (argc!=2 || strcmp(argv[1],"serve")) { fprintf(stderr,"Usage:player-usb-host serve\n");return 2; }
    IOUSBDeviceInterface197 **dev=find_lab();
    if (!dev) { fprintf(stderr,"No lab USB device.\n");return 3; }
    IOReturn rc=(*dev)->USBDeviceOpen(dev);
    if (rc!=kIOReturnSuccess) { (*dev)->Release(dev);fprintf(stderr,"Open failed0x%08x\n",rc);return 4; }
    int failed=status(dev,0);
    unsigned char reply[8]={0};
    if (!failed) failed=control(dev,0xc0,0x56,0,0,reply,8);
    if (!failed && (le16(reply)!=0x4d55 || le16(reply+2)!=2 || le16(reply+4)!=48 || le16(reply+6)!=8)) {
        fprintf(stderr,"Unexpected music capability; stopping.\n");failed=1;
    }
    if (!failed) { puts("{\"ready\":true,\"text_pairs\":48,\"queue\":8}");fflush(stdout); }
    char line[256];
    while (!failed && fgets(line,sizeof(line),stdin)) {
        unsigned a=0,b=0;char extra=0;
        if (!strcmp(line,"quit\n")) break;
        if (!strcmp(line,"event\n")) {
            failed=control(dev,0xc0,0x54,0,0,reply,8);
            if (!failed && le16(reply)!=0x4d45) failed=1;
            if (!failed) printf("{\"seq\":%u,\"button\":%u,\"dropped\":%u}\n",le16(reply+2),le16(reply+4),le16(reply+6));
        } else if (!strncmp(line,"chunk ",6)) {
            char hex[129]={0}; unsigned char block[64];
            if (sscanf(line,"chunk %u %128s %c",&a,hex,&extra)!=2 || a>=2400 || strlen(hex)!=128) {
                puts("{\"error\":\"invalid chunk\"}");fflush(stdout);continue;
            }
            int valid=1;
            for (unsigned i=0;i<64;i++) {
                unsigned byte=0;
                if (!isxdigit((unsigned char)hex[i*2]) || !isxdigit((unsigned char)hex[i*2+1]) || sscanf(hex+i*2,"%2x",&byte)!=1) { valid=0;break; }
                block[i]=(unsigned char)byte;
            }
            if (!valid) { puts("{\"error\":\"invalid hex\"}");fflush(stdout);continue; }
            failed=control(dev,0x40,0x57,0,a,block,64);
            if (!failed) puts("{\"ok\":true}");
        } else if (sscanf(line,"ack %u %c",&a,&extra)==1 && a<=65535) {
            failed=control(dev,0x40,0x55,a,0,NULL,0);
            if (!failed) puts("{\"ok\":true}");
        } else if (sscanf(line,"text %u %u %c",&a,&b,&extra)==2 && a<48 && b<=65535 &&
                   (b&255)>=32 && (b&255)<=126 && (b>>8)>=32 && (b>>8)<=126) {
            failed=control(dev,0x40,0x53,b,a,NULL,0);
            if (!failed) puts("{\"ok\":true}");
        } else if (!strcmp(line,"status\n")) failed=status(dev,1);
        else { puts("{\"error\":\"invalid command\"}");fflush(stdout);continue; }
        if (failed) puts("{\"error\":\"USB request failed; bridge stopped\"}");
        fflush(stdout);
    }
    (*dev)->USBDeviceClose(dev);(*dev)->Release(dev);
    return failed?1:0;
}
