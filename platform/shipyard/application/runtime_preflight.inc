    // A missing ROM archive is built from a supported ROM beside the application,
    // as the desktop extractor does, before the archives are mounted.
    {
        struct RomVersion {
            uint32_t header;
            const char* config;
            bool mq;
        };
        static const RomVersion versions[] = {
            { OOT_NTSC_US_10, "N64_NTSC_10", false },     { OOT_NTSC_US_11, "N64_NTSC_11", false },
            { OOT_NTSC_US_12, "N64_NTSC_12", false },     { OOT_PAL_10, "N64_PAL_10", false },
            { OOT_PAL_11, "N64_PAL_11", false },          { OOT_NTSC_JP_GC_CE, "GC_NMQ_NTSC_J_CE", false },
            { OOT_NTSC_JP_GC, "GC_NMQ_NTSC_J", false },   { OOT_NTSC_US_GC, "GC_NMQ_NTSC_U", false },
            { OOT_PAL_GC, "GC_NMQ_PAL_F", false },        { OOT_PAL_GC_DBG1, "GC_NMQ_D", false },
            { OOT_NTSC_JP_MQ, "GC_MQ_NTSC_J", true },     { OOT_NTSC_US_MQ, "GC_MQ_NTSC_U", true },
            { OOT_PAL_MQ, "GC_MQ_PAL_F", true },          { OOT_PAL_GC_MQ_DBG, "GC_MQ_D", true },
        };
        // Whole-ROM CRC32C values the desktop extractor accepts.
        static const uint32_t accepted[] = {
            0xFA8C0555, 0x8652AC4C, 0x5B8A1EB7, 0x1F731FFE, 0x044B3982, 0xEB15D7B9, 0xDA8E61BF,
            0x7A2FAE68, 0xFD9913B1, 0xE033FBBA, 0x460C938C, 0xD0C76FA9, 0x3496EE47, 0xA25D1262,
            0x15736A58, 0x83B8967D, 0xD61453DE, 0x4129C825, 0x11A4BE61, 0x2BC6C6FD, 0x02CD974C,
        };
        struct Extraction {
            Shipyard::Zapd::Request request;
            volatile LONG finished;
            int result;
            static void Log(const char* message) {
                OutputDebugStringA(message);
                OutputDebugStringA("\n");
            }
            static DWORD WINAPI Run(void* context) {
                Extraction* self = static_cast<Extraction*>(context);
                try {
                    self->result = Shipyard::Zapd::Extract(self->request);
                } catch (...) {
                    self->result = -1;
                }
                InterlockedExchange(&self->finished, 1);
                return 0;
            }
        };
        static const size_t sizes[] = { 32u << 20, 54u << 20, 64u << 20 };
        const std::string root = Ship::Context::GetAppBundlePath();
        bool built[2] = {
            xbox_compat::filesystem::exists(Ship::Context::LocateFileAcrossAppDirs("oot.o2r", appShortName)),
            xbox_compat::filesystem::exists(Ship::Context::LocateFileAcrossAppDirs("oot-mq.o2r", appShortName)),
        };
        const std::vector<std::string> roms =
            built[0] && built[1] ? std::vector<std::string>() : Shipyard::Rom::Find(root);
        char portVersion[24];
        sprintf(portVersion, "%d.%d.%d", gBuildVersionMajor, gBuildVersionMinor, gBuildVersionPatch);
        for (size_t i = 0; i < roms.size(); ++i) {
            // The header names the archive a ROM would build, so a ROM whose archive exists is never read.
            unsigned char head[0x40];
            FILE* file = fopen(roms[i].c_str(), "rb");
            const size_t read = file ? fread(head, 1, sizeof(head), file) : 0;
            if (file)
                fclose(file);
            if (read != sizeof(head) || !Shipyard::Rom::ToBigEndian(head, sizeof(head)))
                continue;
            const uint32_t header = Shipyard::Rom::ReadBig32(&head[0x10]);
            const RomVersion* version = NULL;
            for (size_t v = 0; v < sizeof(versions) / sizeof(versions[0]); ++v)
                if (versions[v].header == header)
                    version = &versions[v];
            if (version == NULL || built[version->mq])
                continue;
            const char* archive = version->mq ? "oot-mq.o2r" : "oot.o2r";
            std::vector<unsigned char> rom;
            if (Shipyard::Rom::Load(roms[i], sizes, 3, rom) != Shipyard::Rom::LoadOk)
                continue;
            // Some MQ debug dumps carry a US region byte; the accepted CRC is of the restored ROM.
            if (header == OOT_PAL_GC_MQ_DBG)
                rom[0x3E] = 'P';
            const uint32_t crc = Shipyard::Rom::Crc32c(&rom[0], rom.size());
            bool known = false;
            for (size_t c = 0; c < sizeof(accepted) / sizeof(accepted[0]); ++c)
                known = known || accepted[c] == crc;
            if (!known)
                continue;

            volatile size_t done = 0, total = 0;
            Extraction job;
            job.request.xmlDirectory = root + "/assets/xml/" + version->config;
            job.request.fileListDirectory = root + "/assets/filelists";
            job.request.configPath = root + "/assets/Config_" + version->config + ".xml";
            job.request.outputPath = xbox_compat::filesystem::path(root + "/" + archive).make_preferred().string();
            job.request.portVersion = portVersion;
            job.request.rom = &rom;
            job.request.done = &done;
            job.request.total = &total;
            job.request.log = &Extraction::Log;
            std::string stages;
            job.request.stages = &stages;
            job.request.helpers = 3;
            // One assets.zip copies to the console far faster than the thousands of files it replaces.
            if (xbox_compat::filesystem::exists(root + "/assets.zip"))
                job.request.assetBundle = root + "/assets.zip";
            job.finished = 0;
            job.result = -1;
            const DWORD start = GetTickCount();
            // Free memory before and at its lowest during extraction, for the boot log.
            MEMORYSTATUS memory;
            GlobalMemoryStatus(&memory);
            const SIZE_T freeBefore = memory.dwAvailPhys;
            SIZE_T freeLeast = freeBefore;
            // A desktop-sized stack, on the hardware thread Shipyard::Async::ServiceProcessor names.
            HANDLE thread = CreateThread(NULL, 1024 * 1024, &Extraction::Run, &job, CREATE_SUSPENDED, NULL);
            if (thread == NULL) {
                Shipyard::Platform::ShowError(L"Ship of Harkinian ROM extraction", L"The extraction thread could not start.");
                exit(1);
            }
            XSetThreadProcessor(thread, 3);
            ResumeThread(thread);
            const std::string name = xbox_compat::filesystem::path(roms[i]).filename().string();
            const std::shared_ptr<Ship::Gui> gui = sohFast3dWindow->GetGui();
            while (!job.finished) {
                sohFast3dWindow->HandleEvents();
                if (!sohFast3dWindow->IsFrameReady())
                    continue;
                GlobalMemoryStatus(&memory);
                if (memory.dwAvailPhys < freeLeast)
                    freeLeast = memory.dwAvailPhys;
                gui->StartDraw();
                sohFast3dWindow->StartFrame();
                sohFast3dWindow->RunGuiOnly();
                if (!ImGui::IsPopupOpen("ROM Extraction"))
                    ImGui::OpenPopup("ROM Extraction");
                if (ImGui::BeginPopupModal("ROM Extraction", NULL,
                                           ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoMove |
                                               ImGuiWindowFlags_NoSavedSettings)) {
                    const float progress = total > 0 ? (float)done / (float)total : 0.0f;
                    char overlay[16];
                    sprintf(overlay, "%.0f%%", progress * 100.0f);
                    ImGui::Text("Extracting %s to %s... %.0f s", name.c_str(), archive,
                                (GetTickCount() - start) / 1000.0f);
                    ImGui::ProgressBar(progress, ImVec2(600.0f, 50.0f), done > 0 ? overlay : "Starting Up");
                    ImGui::EndPopup();
                }
                gui->EndDraw();
                sohFast3dWindow->EndFrame();
            }
            WaitForSingleObject(thread, INFINITE);
            CloseHandle(thread);
            char stage[1024];
            _snprintf_s(stage, sizeof(stage), _TRUNCATE, "extracted %s from %s in %.1f s result=%d free=%u/%u MB %s", archive,
                        name.c_str(), (GetTickCount() - start) / 1000.0f, job.result, (unsigned)(freeLeast >> 20),
                        (unsigned)(freeBefore >> 20), stages.c_str());
            Shipyard::Platform::RecordBootStage(stage, false);
            built[version->mq] = true;
            if (job.result != 0) {
                std::error_code ignored;
                xbox_compat::filesystem::remove(job.request.outputPath, ignored);
                Shipyard::Platform::ShowError(L"Ship of Harkinian ROM extraction",
                                              L"Building the ROM archive failed. Check that assets.zip or the assets "
                                              L"folder from the release is beside the application.");
                exit(1);
            }
        }
    }
    // The archives are mounted here, before the version reader, so it reads the
    // mounted archives instead of indexing temporary copies.
    std::string mqPath = Ship::Context::LocateFileAcrossAppDirs("oot-mq.o2r", appShortName);
    if (xbox_compat::filesystem::exists(mqPath)) {
        context->GetResourceManager()->GetArchiveManager()->AddArchive(mqPath);
    }
    std::string ootPath = Ship::Context::LocateFileAcrossAppDirs("oot.o2r", appShortName);
    if (xbox_compat::filesystem::exists(ootPath)) {
        context->GetResourceManager()->GetArchiveManager()->AddArchive(ootPath);
    }
    const OTRVersion vanillaVersion = DetectOTRVersion("oot.o2r", false);
    const OTRVersion mqVersion = DetectOTRVersion("oot-mq.o2r", true);
    const bool vanillaExists = xbox_compat::filesystem::exists(
        Ship::Context::LocateFileAcrossAppDirs("oot.o2r", appShortName));
    const bool mqExists = xbox_compat::filesystem::exists(
        Ship::Context::LocateFileAcrossAppDirs("oot-mq.o2r", appShortName));
    const Shipyard::Application::ArchivePreflight result = Shipyard::Application::CheckArchives(
        sohArchiveVersionMatch, VerifyArchiveVersion(vanillaVersion), VerifyArchiveVersion(mqVersion),
        vanillaExists, mqExists);
    if (result != Shipyard::Application::ArchivesReady) {
        const wchar_t* message = L"No ROM archives found. Copy an Ocarina of Time ROM (.z64, .n64 or .v64) beside the application and restart it.";
        if (result == Shipyard::Application::PortArchiveMismatch)
            message = L"soh.o2r is missing or does not match this application version. Copy soh.o2r from the matching stable release beside the application.";
        else if (result == Shipyard::Application::GameArchiveMismatch)
            message = L"oot.o2r or oot-mq.o2r is from an incompatible SoH version. Delete it and restart to rebuild it from your ROM.";
        Shipyard::Platform::ShowError(L"Ship of Harkinian archives", message);
        exit(1);
    }
    CheckAndCreateModFolder();
