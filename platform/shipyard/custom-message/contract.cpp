#include <iostream>
#include <sstream>
#include <iomanip>
#include <locale>
static std::string hexBytes(const std::string& s) { const char* h="0123456789abcdef";std::string out;for(size_t i=0;i<s.size();++i){unsigned char c=s[i];out+=h[c>>4];out+=h[c&15];}return out; }
static void show(const char* label,const std::string& s){std::cout<<label<<":"<<s.size()<<":"<<hexBytes(s)<<"\n";}
static void showMessage(const char* label,const CustomMessage& m){std::cout<<label<<":"<<int(m.GetTextBoxType())<<":"<<int(m.GetTextBoxPosition())<<"\n";for(int lang=0;lang<3;++lang)show("language",m.GetForLanguage(lang,MF_RAW));}
int main(){
    std::ostringstream logging;
    auto sink=std::make_shared<spdlog::sinks::ostream_sink_mt>(logging);
    auto logger=std::make_shared<spdlog::logger>("custom-message-contract",sink);
    logger->set_pattern("%v");logger->set_level(spdlog::level::debug);spdlog::set_default_logger(logger);
    SHIPYARD_MESSAGE_LAYOUT
    SHIPYARD_MESSAGE_LITERALS
    show("QM_WHITE",QM_WHITE);show("HS_HBA",HS_HORSE_ARCHERY);
    show("END",CustomMessage::MESSAGE_END());show("NL",CustomMessage::NEWLINE());show("WAIT",CustomMessage::WAIT_FOR_INPUT());show("PLAYER",CustomMessage::PLAYER_NAME());show("CHOICE",CustomMessage::TWO_WAY_CHOICE());
    show("WHITE",CustomMessage::COLOR(QM_WHITE));show("POINTS",CustomMessage::POINTS(HS_HORSE_ARCHERY));
    for(int n=0;n<256;++n)show("icon",CustomMessage::ITEM_OBTAINED(static_cast<uint8_t>(n)));
    std::string charset;
    std::map<std::string,char> charsetSorted(textBoxSpecialCharacters.begin(),textBoxSpecialCharacters.end());
    for(auto item:charsetSorted){show("charset-key",item.first);show("charset-value",std::string(1,item.second));charset+=item.first+" ";}
    CustomMessage transform;
    std::string converted=charset;transform.ReplaceSpecialCharacters(converted);show("charset-all",converted);
    std::vector<char> raw(charset.begin(),charset.end());raw.push_back(0);const char* result=Interface_ReplaceSpecialCharacters(raw.data());show("charset-interface",result);delete[] result;
    char nulChars[]={'A',0,static_cast<char>(0xC3),static_cast<char>(0xA9),0};result=Interface_ReplaceSpecialCharacters(nulChars);show("interface-nul",result);delete[] result;
    for(auto item:pixelWidthTable){show("pixel-key",item.first);std::cout<<"pixel-width:"<<item.second<<"\n";}
    for(auto item:std::map<std::string,std::string>(percentColors.begin(),percentColors.end())){show("percent-key",item.first);show("percent-value",item.second);}
    for(auto item:std::map<std::string,std::string>(colorToPercent.begin(),colorToPercent.end())){show("color-key",item.first);show("color-value",item.second);}
    for(auto item:std::map<std::string,ItemID>(altarIcons.begin(),altarIcons.end())){show("altar-key",item.first);std::cout<<"altar-value:"<<int(item.second)<<"\n";}
    std::vector<std::string> colors;colors.push_back(QM_RED);colors.push_back(QM_BLUE);colors.push_back(QM_WHITE);
    std::vector<bool> capital;capital.push_back(true);capital.push_back(false);
    CustomMessage source("#hello# @&%gworld%w^$0 prize #red#", "#hallo# @&%gWelt%w^$1 Preis #rot#", "#salut# @&%gmonde%w^$2 prix #rouge#",colors,capital,TEXTBOX_TYPE_BLUE,TEXTBOX_POS_TOP);
    for(int format=MF_FORMATTED;format<=MF_ENCODE;++format){for(int lang=0;lang<3;++lang)show("format",source.GetForLanguage(lang,static_cast<MessageFormat>(format)));auto all=source.GetAllMessages(static_cast<MessageFormat>(format));for(auto value:all)show("all-messages",value);}
    showMessage("source-after-get",source);
    CustomMessage fallback("English",TODO_TRANSLATE " German",TODO_TRANSLATE);showMessage("fallback",fallback);
    showMessage("default",CustomMessage());showMessage("one-language",CustomMessage("only"));
    showMessage("text-constructor",CustomMessage(Text("EN","FR","DE")));
    showMessage("color-constructor",CustomMessage("only",colors,capital));
    CustomMessage properties=source;properties.SetColors(colors);properties.SetCapital(capital);properties.SetTextBoxType(TEXTBOX_TYPE_BLACK);properties.SetTextBoxPosition(TEXTBOX_POS_MIDDLE);
    for(auto value:properties.GetColors())show("get-color",value);for(bool value:properties.GetCapital())std::cout<<"get-capital:"<<value<<"\n";
    showMessage("properties",properties);show("get-english",source.GetEnglish());show("get-german",source.GetGerman());show("get-french",source.GetFrench());
    CustomMessage appended=source+CustomMessage("end","Ende","fin",colors,capital);showMessage("plus-message",appended);
    showMessage("plus-string",source+std::string("!"));appended=source;appended+=std::string("!");showMessage("append-string",appended);appended+=source;showMessage("append-message",appended);
    std::cout<<"equality:"<<(CustomMessage("same","x","y")==CustomMessage("same","a","b"))<<":"<<(CustomMessage("x","y","z")==std::string("y"))<<":"<<(CustomMessage("x")!=CustomMessage("y"))<<"\n";
    CustomMessage replacement("[[1]] and [[2]]", "[[1]] und [[2]]", "[[1]] et [[2]]",colors,capital);
    std::vector<CustomMessage> names;names.push_back(CustomMessage("alpha"));names.push_back(CustomMessage("beta","Beta","bete"));replacement.InsertNames(names);showMessage("insert-names",replacement);
    replacement.Replace(std::string("beta"),std::string("B"));replacement.Capitalize();showMessage("capitalize-copy-semantics",replacement);
    replacement=CustomMessage("replace EN", "replace DE", "replace FR");replacement.Replace(std::string("replace"),CustomMessage("english","deutsch","francais"));showMessage("replace-message",replacement);
    CustomMessage embedded(std::string("A\0B",3),std::string("C\0D",3),std::string("E\0F",3));embedded.Format();showMessage("embedded-nul",embedded);
    for(unsigned n=0;n<256;++n){CustomMessage number("[[d]] |apple|apples|", "[[d]] |Apfel|Aepfel|", "[[d]] |pomme|pommes|");number.InsertNumber(static_cast<uint8_t>(n));showMessage("number",number);}
    CustomMessage plural("apples\xE2\x82\xAC |is|are|", "Apfel |ist|sind|", "pommes\xE2\x82\xAC |est|sont|");plural.SetSingularPlural();showMessage("plural",plural);
    CustomMessage changed=source;changed.Format(ITEM_KOKIRI_EMERALD);showMessage("format-item",changed);changed=source;changed.Clean();showMessage("clean",changed);changed=source;changed.Encode();showMessage("encode",changed);
    std::string longText;for(int n=0;n<45;++n)longText+="Words, " + charset + "@ %rcolored%w words. ";
    std::vector<std::string> wrapCases;wrapCases.push_back(longText);wrapCases.push_back("one&two&three&four&five&six^page");wrapCases.push_back("Would you like a prize?\x1BYes&No");wrapCases.push_back("unlisted \xF0\x9F\x98\x80 bytes with enough spaces. ");wrapCases.push_back(std::string("A\0B and words.",14));
    for(auto sample:wrapCases){CustomMessage m(sample,sample,sample);m.AutoFormat();showMessage("auto",m);m=CustomMessage(sample,sample,sample);m.AutoFormat(ITEM_BOW);showMessage("auto-icon",m);}
    for(unsigned n=1;n<=120;++n){std::string sample(n,'W');sample+=" end.";std::cout<<"line-length:"<<n<<":"<<NextLineLength(&sample,0,false)<<":"<<NextLineLength(&sample,0,true)<<"\n";}
    const unsigned char controls[]={5,6,7,12,14,17,18,19,20,21,30};for(auto c:controls){std::string codes;codes+=char(c);codes+=char(1);codes+="x";codes+=char(1);codes+="tail";std::cout<<"find-newline:"<<int(c)<<":"<<transform.FindNEWLINE(codes,0)<<"\n";}
    const char* breaks[]={"a b","a&b","a^b","abc"};for(auto sample:breaks){std::string s(sample);std::cout<<"break-result:"<<transform.AddBreakString(s,0,"&")<<"\n";show("break",s);}
    CustomMessageManager manager;std::cout<<"tables:"<<manager.CreateMessage("missing",1,source)<<":"<<manager.ClearMessageTable("missing")<<":"<<manager.AddCustomMessageTable("test")<<":"<<manager.AddCustomMessageTable("test")<<":"<<manager.CreateMessage("test",1,source)<<":"<<manager.CreateMessage("test",1,source)<<"\n";
    for(int format=0;format<=MF_ENCODE;++format)showMessage("retrieve",manager.RetrieveMessage("test",1,static_cast<MessageFormat>(format)));
    std::cout<<"get-item:"<<manager.CreateGetItemMessage("test",2,ITEM_OCARINA_TIME,source)<<"\n";showMessage("get-item-value",manager.RetrieveMessage("test",2));
    try{manager.RetrieveMessage("missing",88);}catch(const MessageNotFoundException& e){show("missing-table",e.what());}
    try{manager.RetrieveMessage("test",88);}catch(const MessageNotFoundException& e){show("missing-message",e.what());}
    std::cout<<"clear:"<<manager.ClearMessageTable("test")<<"\n";try{manager.RetrieveMessage("test",1);}catch(const MessageNotFoundException& e){show("cleared-message",e.what());}
    logger->flush();show("logging",logging.str());
}
