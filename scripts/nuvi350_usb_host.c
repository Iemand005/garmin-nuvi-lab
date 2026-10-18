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

static int info350(IOUSBDeviceInterface197 **dev,int print) {
    unsigned char reply[16]={0};
    if (control(dev,0xc0,0x58,0,0,reply,16)) return 1;
    unsigned width=le16(reply+8),height=le16(reply+10);
    unsigned prefix=le16(reply+12)|((unsigned)le16(reply+14)<<16);
    if (le16(reply)!=0x3530 || le16(reply+2)!=1 || le16(reply+4)!=476 || le16(reply+6)!=620 ||
        !((width==320 && height==240) || (width==240 && height==320)) ||
        !(prefix==0x11fb4fc0 || prefix==0x11fda7e0)) {
        fprintf(stderr,"Unexpected350 identity/display profile.\n");return 1;
    }
    if (print) printf("{\"model\":\"nuvi350\",\"hwid\":476,\"software\":620,\"width\":%u,\"height\":%u,\"prefix\":%u}\n",width,height,prefix);
    return 0;
}

int main(int argc,char **argv) {
    if (argc==2 && strcmp(argv[1],"--help")==0) {
        puts("nuvi350-usb-host serve\nJSON-line replies; commands:info,snapshot,raw,event,ack SEQ,text INDEX WORD,chunk INDEX HEX,status,quit. Requires350 USB/display-only capability.");
        return 0;
    }
    if (argc!=2 || strcmp(argv[1],"serve")) { fprintf(stderr,"Usage:nuvi350-usb-host serve\n");return 2; }
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
    if (!failed) failed=info350(dev,0);
    if (!failed) { puts("{\"ready\":true,\"text_pairs\":48,\"queue\":8}");fflush(stdout); }
    char line[256];
    while (!failed && fgets(line,sizeof(line),stdin)) {
        unsigned a=0,b=0;char extra=0;
        if (!strcmp(line,"quit\n")) break;
        if (!strcmp(line,"raw\n")) {
            unsigned char data[16]={0};
            failed=control(dev,0xc0,0x5a,0,0,data,16);
            if (!failed && (le16(data)!=0x3558 || le16(data+2)!=1)) failed=1;
            if (!failed) printf("{\"flags\":%u,\"a\":%u,\"b\":%u,\"failed_transfer\":%u,\"spi_status\":%u,\"gpio_in\":%u,\"valid\":%s}\n",
                le16(data+4),le16(data+6),le16(data+8),le16(data+10),le16(data+12),le16(data+14),
                le16(data+4)==3 ? "true" : "false");
        } else if (!strcmp(line,"snapshot\n")) {
            unsigned values[9]={0};
            for (unsigned page=0;page<3 && !failed;page++) {
                unsigned char data[16]={0};
                failed=control(dev,0xc0,0x59,0,page,data,16);
                if (!failed && (le16(data)!=0x3554 || le16(data+2)!=page)) failed=1;
                if (!failed) for (unsigned j=0;j<3;j++)
                    values[page*3+j]=le16(data+4+j*4)|((unsigned)le16(data+6+j*4)<<16);
            }
            if (!failed) printf("{\"gpio_in\":%u,\"gpio_out\":%u,\"gpio_direction\":%u,\"spi_set1\":%u,\"spi_set2\":%u,\"spi_control\":%u,\"spi_status\":%u,\"spi_sysstatus\":%u,\"spi_revision\":%u,\"pen_down\":%s}\n",
                values[0],values[1],values[2],values[3],values[4],values[5],values[6],values[7],values[8],
                (values[0] & (1u<<14)) ? "false" : "true");
        } else if (!strcmp(line,"event\n")) {
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
        } else if (!strcmp(line,"info\n")) failed=info350(dev,1);
        else if (!strcmp(line,"status\n")) failed=status(dev,1);
        else { puts("{\"error\":\"invalid command\"}");fflush(stdout);continue; }
        if (failed) puts("{\"error\":\"USB request failed; bridge stopped\"}");
        fflush(stdout);
    }
    (*dev)->USBDeviceClose(dev);(*dev)->Release(dev);
    return failed?1:0;
}
