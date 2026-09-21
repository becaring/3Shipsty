#include <opus/opus.h>
#include <opusfile.h>
#include <ogg/ogg.h>
#include <vector>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

static void require(bool condition, const char* message) {
    if (!condition) { std::fprintf(stderr, "%s\n", message); std::exit(1); }
}
static void pages(ogg_stream_state* stream, std::vector<unsigned char>& data) {
    ogg_page page;
    while (ogg_stream_flush(stream, &page)) {
        data.insert(data.end(), page.header, page.header + page.header_len);
        data.insert(data.end(), page.body, page.body + page.body_len);
    }
}
static void packet(ogg_stream_state* stream, std::vector<unsigned char>& data,
                   unsigned char* bytes, long length, long number, ogg_int64_t granule, bool end) {
    ogg_packet value = {};
    value.packet=bytes; value.bytes=length; value.packetno=number;
    value.b_o_s=number==0; value.e_o_s=end; value.granulepos=granule;
    require(ogg_stream_packetin(stream, &value)==0, "Ogg packet insertion failed");
    pages(stream,data);
}
static std::vector<opus_int16> decode(OggOpusFile* file) {
    std::vector<opus_int16> output;
    opus_int16 block[2048]; int count;
    while ((count=op_read(file,block,2048,NULL))>0)
        output.insert(output.end(),block,block+count*2);
    require(count==0,"Opus decode error");
    return output;
}
int main(int argc,char** argv) {
    require(argc==2,"Expected an owned fixture output path");
    int error=0, lookahead=0;
    OpusEncoder* encoder=opus_encoder_create(48000,2,OPUS_APPLICATION_AUDIO,&error);
    require(encoder && error==OPUS_OK,"Encoder creation failed");
    require(opus_encoder_ctl(encoder,OPUS_GET_LOOKAHEAD(&lookahead))==OPUS_OK,"Lookahead failed");
    require(opus_encoder_ctl(encoder,OPUS_SET_BITRATE(96000))==OPUS_OK,"Bitrate failed");
    ogg_stream_state stream;
    require(ogg_stream_init(&stream,923)==0,"Ogg initialization failed");
    std::vector<unsigned char> bytes;
    // Ogg Opus serialized fields are little-endian, independent of host order.
    unsigned char head[19]={'O','p','u','s','H','e','a','d',1,2,0,0,0x80,0xbb,0,0,0,0,0};
    head[10]=(unsigned char)lookahead; head[11]=(unsigned char)(lookahead>>8);
    unsigned char tags[16]={'O','p','u','s','T','a','g','s',0,0,0,0,0,0,0,0};
    packet(&stream,bytes,head,19,0,0,false);
    packet(&stream,bytes,tags,16,1,0,false);
    for (int frame=0;frame<12;++frame) {
        float pcm[960*2]; unsigned char encoded[4000];
        for(int i=0;i<960;++i) {
            double t=(frame*960+i)/48000.0;
            pcm[i*2]=(float)(.2*std::sin(t*440*6.283185307179586));
            pcm[i*2+1]=(float)(.3*std::sin(t*659*6.283185307179586));
        }
        int length=opus_encode_float(encoder,pcm,960,encoded,sizeof(encoded));
        require(length>0,"Encoding failed");
        packet(&stream,bytes,encoded,length,frame+2,(frame+1)*960,frame==11);
    }
    ogg_stream_clear(&stream); opus_encoder_destroy(encoder);
    OggOpusFile* file=op_open_memory(&bytes[0],bytes.size(),&error);
    require(file && !error,"Memory open failed");
    require(op_channel_count(file,-1)==2 && op_seekable(file),"Stream properties failed");
    ogg_int64_t total=op_pcm_total(file,-1);
    require(total==12*960-lookahead,"Granule/pre-skip accounting failed");
    std::vector<opus_int16> full=decode(file);
    require(full.size()==(size_t)total*2,"Decoded PCM length differs");
    require(op_pcm_tell(file)==total,"PCM cursor at EOF differs");
    op_free(file);
    file=op_open_memory(&bytes[0],bytes.size(),&error);
    require(file && !error,"Second memory open failed");
    // Noise-shaped dither state intentionally differs after seeking. Compare
    // sample alignment with the public dither switch off; keep default dither
    // for the separate complete memory/file comparison below.
    op_set_dither_enabled(file,0);
    std::vector<opus_int16> undithered=decode(file);
    require(op_pcm_seek(file,1000)==0 && op_pcm_tell(file)==1000,"PCM seek failed");
    std::vector<opus_int16> tail=decode(file);
    require(tail.size()==undithered.size()-2000,"Seek length differs");
    require(std::memcmp(&tail[0],&undithered[2000],tail.size()*sizeof(opus_int16))==0,"Seek PCM differs");
    require(op_pcm_seek(file,total+1)!=0,"Out-of-range seek unexpectedly succeeded");
    op_free(file);
    FILE* output=std::fopen(argv[1],"wb"); require(output!=NULL,"Fixture creation failed");
    require(std::fwrite(&bytes[0],1,bytes.size(),output)==bytes.size(),"Fixture write failed");
    require(std::fclose(output)==0,"Fixture close failed");
    file=op_open_file(argv[1],&error); require(file && !error,"File open failed");
    require(decode(file)==full,"File and memory PCM differ"); op_free(file);
    unsigned char invalid[20]={}; file=op_open_memory(invalid,sizeof(invalid),&error);
    require(!file && error<0,"Malformed input was accepted");
    double energy=0; for(size_t i=0;i<full.size();++i) energy+=double(full[i])*full[i];
    require(energy/full.size()>1000000,"Decoded audio unexpectedly silent");
    std::printf("Opus memory/file decode, Ogg pre-skip, PCM seek, EOF and malformed input pass: %lld stereo frames\n",(long long)total);
    return 0;
}
