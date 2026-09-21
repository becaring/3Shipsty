#include "gfxd.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint64_t hash=1469598103934665603ULL;
static void digest(const void* data,size_t size){const unsigned char* p=data;while(size--){hash^=*p++;hash*=1099511628211ULL;}}
int main(void){
    const gfxd_ucode_t targets[]={gfxd_f3d,gfxd_f3db,gfxd_f3dex,gfxd_f3dexb,gfxd_f3dex2};
    char reference[2048],output[2048];int firstResult=0,cases=0;
    for(int target=0;target<5;++target){
        gfxd_target(targets[target]);gfxd_enable(gfxd_emit_dec_color);gfxd_disable(gfxd_stop_on_invalid);
        for(unsigned opcode=0;opcode<256;++opcode)for(unsigned pattern=0;pattern<4;++pattern){
            uint32_t words[4]={(opcode<<24)|(pattern?0x123456:0),pattern*0x55667788u,target==4?0xdf000000u:0xb8000000u,0};
            for(int endian=0;endian<3;++endian){
                unsigned char bytes[sizeof(words)];
                for(size_t i=0;i<4;++i)for(int j=0;j<4;++j)bytes[4*i+j]=(unsigned char)(words[i]>>(8*(endian==gfxd_endian_big?3-j:j)));
                if(endian==gfxd_endian_host)memcpy(bytes,words,sizeof(words));
                memset(output,0,sizeof(output));gfxd_input_buffer(bytes,sizeof(bytes));gfxd_output_buffer(output,sizeof(output));gfxd_endian(endian,4);
                int result=gfxd_execute();assert(memchr(output,0,sizeof(output))!=NULL);
                if(endian==0){strcpy(reference,output);firstResult=result;}
                else assert(strcmp(reference,output)==0&&result==firstResult);
                digest(&result,sizeof(result));digest(output,strlen(output));++cases;
            }
        }
    }
    // The UI packs host-native uint32 words, exactly the host-mode case above.
    // Bounded formatting must retain C99 full-length/truncation behavior.
    char text[700];memset(text,'x',sizeof(text)-1);text[sizeof(text)-1]=0;
    memset(output,0,sizeof(output));gfxd_output_buffer(output,sizeof(output));
    int written=gfxd_printf("%s",text);assert(written==255&&strlen(output)==255);
    printf("%d five-ucode/opcode/pattern/endian disassemblies and bounded formatting; hash %llu\n",cases,(unsigned long long)hash);
    return 0;
}
