/* Mac host for the private RAM-only EP0 experiment. No stock-device commands.
 * Build: xcrun clang -Wall -Wextra -Werror -Wno-deprecated-declarations
 *   -framework IOKit -framework CoreFoundation scripts/usb_lab_host.c
 *   -o analysis/usb/usb-lab-host
 */
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <IOKit/IOCFPlugIn.h>
#include <IOKit/usb/IOUSBLib.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static uint16_t le16(const unsigned char *p) { return p[0] | ((uint16_t)p[1]<<8); }

static IOUSBDeviceInterface197 **find_lab(void) {
    CFMutableDictionaryRef match=IOServiceMatching("IOUSBDevice");
    if (!match) return NULL;
    int vendor=0x091e,product=0xfffe;
    CFNumberRef v=CFNumberCreate(NULL,kCFNumberIntType,&vendor);
    CFNumberRef p=CFNumberCreate(NULL,kCFNumberIntType,&product);
    CFDictionarySetValue(match,CFSTR("idVendor"),v);
    CFDictionarySetValue(match,CFSTR("idProduct"),p);
    CFRelease(v); CFRelease(p);
    io_iterator_t iterator=0;
    if (IOServiceGetMatchingServices(kIOMainPortDefault,match,&iterator)!=KERN_SUCCESS) return NULL;
    IOUSBDeviceInterface197 **found=NULL;
    io_service_t service;
    while ((service=IOIteratorNext(iterator))) {
        IOCFPlugInInterface **plugin=NULL;
        SInt32 score=0;
        IOReturn rc=IOCreatePlugInInterfaceForService(service,kIOUSBDeviceUserClientTypeID,
                                                    kIOCFPlugInInterfaceID,&plugin,&score);
        IOObjectRelease(service);
        if (rc!=kIOReturnSuccess || !plugin) continue;
        IOUSBDeviceInterface197 **candidate=NULL;
        HRESULT hr=(*plugin)->QueryInterface(plugin,CFUUIDGetUUIDBytes(kIOUSBDeviceInterfaceID197),
                                             (LPVOID*)&candidate);
        IODestroyPlugInInterface(plugin);
        if (hr || !candidate) continue;
        UInt16 actual_v=0,actual_p=0;
        (*candidate)->GetDeviceVendor(candidate,&actual_v);
        (*candidate)->GetDeviceProduct(candidate,&actual_p);
        if (actual_v!=vendor || actual_p!=product) {
            (*candidate)->Release(candidate);
            continue;
        }
        if (found) {
            (*candidate)->Release(candidate);
            (*found)->Release(found);
            found=NULL;
            fprintf(stderr,"Multiple lab devices; connect only one.\n");
            break;
        }
        found=candidate;
    }
    IOObjectRelease(iterator);
    return found;
}

static int status(IOUSBDeviceInterface197 **dev,int print) {
    unsigned char reply[16]={0};
    IOUSBDevRequestTO req={0};
    req.noDataTimeout=1000; req.completionTimeout=2000;
    req.bmRequestType=0xc0; req.bRequest=0x52;
    req.wLength=sizeof(reply); req.pData=reply;
    IOReturn rc=(*dev)->DeviceRequestTO(dev,&req);
    if (rc!=kIOReturnSuccess || req.wLenDone!=sizeof(reply)) {
        fprintf(stderr,"Lab status failed: 0x%08x, %u bytes\n",rc,(unsigned)req.wLenDone);
        return 1;
    }
    if (le16(reply)!=0x4c47 || le16(reply+2)!=1) {
        fprintf(stderr,"Unexpected lab protocol identity; no value sent.\n"); return 1;
    }
    if (print) printf("{\"value\":%u,\"x\":%u,\"y\":%u,\"contact\":%u,\"color\":%u,\"configured\":%u}\n",
                      le16(reply+4),le16(reply+6),le16(reply+8),le16(reply+10),le16(reply+12),le16(reply+14));
    return 0;
}

int main(int argc,char **argv) {
    int watch=0,set=0,value=0;
    if (argc==2 && strcmp(argv[1],"--help")==0) {
        puts("usb-lab-host status | watch | set 0..999\nOnly matches private RAM lab USB identity 091e:fffe; never stock Garmin storage/preboot.");
        return 0;
    }
    if (argc==2 && strcmp(argv[1],"status")==0) { }
    else if (argc==2 && strcmp(argv[1],"watch")==0) watch=1;
    else if (argc==3 && strcmp(argv[1],"set")==0) {
        char *end=NULL;
        long number=strtol(argv[2],&end,10);
        if (!*argv[2] || *end || number<0 || number>999) { fprintf(stderr,"Value must be0..999.\n"); return 2; }
        set=1; value=(int)number;
    } else { fprintf(stderr,"Usage: usb-lab-host status | watch | set 0..999\n"); return 2; }
    IOUSBDeviceInterface197 **dev=find_lab();
    if (!dev) { fprintf(stderr,"No RAM lab device (091e:fffe) found.\n"); return 3; }
    IOReturn rc=(*dev)->USBDeviceOpen(dev);
    if (rc!=kIOReturnSuccess) {
        fprintf(stderr,"Lab open failed: 0x%08x\n",rc); (*dev)->Release(dev); return 4;
    }
    int result=status(dev,!watch && !set);
    if (!result) {
        UInt8 configuration=0;
        rc=(*dev)->GetConfiguration(dev,&configuration);
        if (rc==kIOReturnSuccess && configuration==0) rc=(*dev)->SetConfiguration(dev,1);
        if (rc!=kIOReturnSuccess) { fprintf(stderr,"Lab configure failed:0x%08x\n",rc); result=6; }
    }
    if (!result && set) {
        IOUSBDevRequestTO req={0};
    req.noDataTimeout=1000; req.completionTimeout=2000;
        req.bmRequestType=0x40; req.bRequest=0x51; req.wValue=(UInt16)value;
        rc=(*dev)->DeviceRequestTO(dev,&req);
        if (rc!=kIOReturnSuccess) { fprintf(stderr,"Lab set failed:0x%08x\n",rc); result=5; }
        else result=status(dev,1);
    }
    if (!result && watch) {
        for (int i=0;i<150;i++) {
            if ((result=status(dev,1))) break;
            fflush(stdout); usleep(200000);
        }
    }
    (*dev)->USBDeviceClose(dev);
    (*dev)->Release(dev);
    return result;
}
