#include <StormLib.h>
#include <vector>
#include <cstdio>
#include <cstdlib>
#include <cstring>

static void require(bool value,const char* message) {
    if(!value){std::fprintf(stderr,"%s (error %lu)\n",message,(unsigned long)GetLastError());std::exit(1);}
}
int main(int argc,char** argv) {
    require(argc==3,"Expected owned archive and source paths");
    std::vector<unsigned char> payload(40000);
    for(size_t i=0;i<payload.size();++i)payload[i]=(i%173<120)?0:(unsigned char)(i*97+i/19);
    FILE* fp=std::fopen(argv[2],"wb");require(fp!=NULL,"Source creation failed");
    require(std::fwrite(&payload[0],1,payload.size(),fp)==payload.size(),"Source write failed");
    require(std::fclose(fp)==0,"Source close failed");
    // Both arguments are generated only under the owned contract directory.
    std::remove(argv[1]);
    HANDLE archive=NULL;
    require(SFileCreateArchive(argv[1],MPQ_CREATE_ARCHIVE_V2|MPQ_CREATE_LISTFILE|MPQ_CREATE_ATTRIBUTES,32,&archive),"Create MPQ failed");
    unsigned compressions[]={MPQ_COMPRESSION_ZLIB,MPQ_COMPRESSION_BZIP2,MPQ_COMPRESSION_LZMA,
                             MPQ_COMPRESSION_PKWARE,MPQ_COMPRESSION_SPARSE};
    for(unsigned i=0;i<sizeof(compressions)/sizeof(compressions[0]);++i) {
        char name[80];std::sprintf(name,"contract/encrypted-%u.bin",i);
        require(SFileAddFileEx(archive,argv[2],name,MPQ_FILE_COMPRESS|MPQ_FILE_ENCRYPTED|MPQ_FILE_FIX_KEY,
                              compressions[i],compressions[i]),"Compress/encrypt member failed");
    }
    require(SFileCloseArchive(archive),"Close written MPQ failed");
    require(SFileOpenArchive(argv[1],0,MPQ_OPEN_READ_ONLY,&archive),"Reopen MPQ failed");
    for(unsigned i=0;i<sizeof(compressions)/sizeof(compressions[0]);++i) {
        char name[80];std::sprintf(name,"contract/encrypted-%u.bin",i);
        HANDLE file=NULL;require(SFileOpenFileEx(archive,name,0,&file),"Open member failed");
        require(SFileGetFileSize(file,NULL)==payload.size(),"Member size differs");
        std::vector<unsigned char> actual(payload.size());DWORD read=0;
        require(SFileReadFile(file,&actual[0],(DWORD)actual.size(),&read,NULL),"Read member failed");
        require(read==payload.size() && actual==payload,"Decompressed/decrypted member differs");
        LONG high=0;require(SFileSetFilePointer(file,8191,&high,FILE_BEGIN)==8191,"Member seek failed");
        unsigned char tail[67];require(SFileReadFile(file,tail,sizeof(tail),&read,NULL),"Partial read failed");
        require(read==sizeof(tail) && std::memcmp(tail,&payload[8191],sizeof(tail))==0,"Partial read differs");
        require(SFileCloseFile(file),"Close member failed");
    }
    HANDLE list=NULL;require(SFileOpenFileEx(archive,"(listfile)",0,&list),"Modern OTR listfile lookup failed");
    require(SFileGetFileSize(list,NULL)>0,"Listfile empty");require(SFileCloseFile(list),"Listfile close failed");
    HANDLE missing=NULL;require(!SFileOpenFileEx(archive,"missing",0,&missing),"Missing member accepted");
    require(SFileCloseArchive(archive),"Final archive close failed");
    std::puts("Exact LUS-patched StormLib: encrypted MPQ, zlib/bzip2/LZMA/PKWARE/sparse decode, seeking, listfile and missing-member checks pass");
}
