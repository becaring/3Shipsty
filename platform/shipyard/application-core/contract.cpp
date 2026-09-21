void Print(const std::string& s){
    for(size_t i=0;i<s.size();++i)printf("%02x",(unsigned char)s[i]);
    printf("\n");
}
int main(){
    for(size_t i=0;i<sceneNames.size();++i)Print(SohUtils::GetSceneName(i));
    for(int lang=0;lang<3;++lang){
        gSaveContext.language=lang;
        for(size_t i=0;i<itemNamesEng.size();++i)Print(SohUtils::GetItemName(i));
        for(size_t i=0;i<questItemNamesEng.size();++i)Print(SohUtils::GetQuestItemName(i));
    }
    for(size_t i=0;i<rcareaPrefixes.size();++i)Print(SohUtils::GetRandomizerCheckAreaPrefix(i));
    for(int v=0;v<256;++v){
        std::string s=" \n";s+=char(v);s+="\r\x1a";s+=char(0);s+=" end ";
        Print(SohUtils::Sanitize(s));printf("%u %d\n",SohUtils::Hash(s),SohUtils::IsStringEmpty(s));
        for(size_t len=0;len<16;++len){
            char a[24],b[24];memset(a,0x5a,sizeof(a));memset(b,0x5a,sizeof(b));
            SohUtils::CopyStringToCharArray(a,s,len);
            size_t n=SohUtils::CopyStringToCharBuffer(b,s,len);
            printf("%u:",(unsigned)n);
            for(size_t i=0;i<24;++i)printf("%02x%02x",(unsigned char)a[i],(unsigned char)b[i]);
            printf("\n");
        }
    }
    for(unsigned id=0;id<65536;++id){
        SOH::MessageEntry message;message.id=id;message.textboxType=(id>>8)&15;message.textboxYPos=id&15;message.msg="abc\x01\x7f";
        MessageTableEntry entry;SetMessageEntry(entry,message);
        assert(entry.textId==id && entry.typePos==(((id>>8)&15)<<4 | (id&15)));
        assert(entry.segment==message.msg.c_str() && entry.msgSize==message.msg.size());
    }
    puts("65536 actual message entry conversions preserve pointer lifetime and fields");
}
