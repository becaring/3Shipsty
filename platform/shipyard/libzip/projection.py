"""Generic XDK boundary projection derived from Smash360; see provenance.json."""

def once(text, before, after):
    if text.count(before) != 1: raise ValueError("libzip projection anchor drift: " + before)
    return text.replace(before, after)

def transform(name,text):
    if name=='zip_dirent.c':
        text=once(text,'    zip_uint16_t version_needed;','')
        text=once(text,'    zip_int16_t version_madeby = 63 | (de->version_madeby & 0xff00);','    version_madeby = 63 | (de->version_madeby & 0xff00);')
        text=once(text,'    bool has_changed = false;','    bool has_changed = false;\n    zip_uint16_t version_needed;\n    zip_int16_t version_madeby;')
    elif name=='zip_source_file_win32.h':
        text=once(text,'#include <windows.h>','#ifdef _XBOX\n#include <xtl.h>\n#else\n#include <windows.h>\n#endif')
        text=once(text,'#include <aclapi.h>','#ifdef HAVE_GETSECURITYINFO\n#include <aclapi.h>\n#endif')
    elif name=='zip_source_file_win32.c':
        # Xbox does not expose GetFileType; never guess arbitrary handle type.
        start=text.index('    return zip_source_file_common_new(NULL, h,')
        end=text.index('\n}',start)
        text=text[:start]+'    zip_error_set(error, ZIP_ER_OPNOTSUPP, 0);\n    return NULL;'+text[end:]
        start=text.index('    if (GetFileType(h) == FILE_TYPE_DISK)')
        end=text.index('\n    /* TODO:',start)
        text=text[:start]+'    zip_error_set(&ctx->error, ZIP_ER_OPNOTSUPP, 0);\n    return false;\n'+text[end:]
    elif name=='zip_source_file_win32_named.c':
        text=text.replace('INVALID_FILE_ATTRIBUTES','((DWORD)-1)')
        text=once(text,'    PSECURITY_DESCRIPTOR psd = NULL;','    void *psd = NULL;')
        start=text.index('            if (file_attributes.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)')
        end=text.index('\n        }',start)
        text=text[:start]+'            st->regular_file = true;'+text[end:]
        text=text.replace('(FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_DEVICE)','FILE_ATTRIBUTE_DIRECTORY')
        # Desktop handle has been consumed before attribute/rename failures.
        text=once(text,'    attributes = file_ops->get_file_attributes(ctx->tmpname);','    ctx->fout = NULL;\n    attributes = file_ops->get_file_attributes(ctx->tmpname);')
    elif name=='zip_source_file_win32_utf8.c':
        start=text.index('    int size;',text.index('zip_source_file_create('))
        text=text[:start]+'''    char *resolved;
    zip_source_t *source;
    if (fname == NULL || length < ZIP_LENGTH_UNCHECKED) {
        zip_error_set(error, ZIP_ER_INVAL, 0);
        return NULL;
    }
    resolved = shipyard_zip_resolve_path(fname, error);
    if (resolved == NULL) return NULL;
    source = zip_source_win32a_create(resolved, start, length, error);
    free(resolved);
    return source;
}
'''
        text=once(text,'#include "zip_source_file_win32.h"','#include "zip_source_file_win32.h"\n#include "libzip/native_boundary.h"')
    elif name=='zip_source_file_win32_utf16.c':
        # Keep real public validation/error ownership; no native wide-file API.
        start=text.index('ZIP_EXTERN zip_source_t *')
        end=text.index('\n\nstatic char *',start)
        methods=text[start:end]
        old='    return zip_source_file_common_new((const char *)fname, NULL, start, length, NULL, &_zip_source_file_win32_named_ops, &ops_utf16, error);'
        methods=once(methods,old,'    zip_error_set(error, ZIP_ER_OPNOTSUPP, 0);\n    return NULL;')
        text=text[:text.index('#include "zip_source_file_win32.h"')]+'#include "zip_source_file_win32.h"\n'+methods+'\n'
    elif name=='zip_random_win32.c':
        start=text.index('#include <windows.h>');end=text.index('#ifndef HAVE_RANDOM_UINT32')
        text=text[:start]+'''#include "libzip/native_boundary.h"
ZIP_EXTERN bool
zip_secure_random(zip_uint8_t *buffer, zip_uint16_t length) {
    return shipyard_zip_secure_random(buffer, length) != 0;
}

'''+text[end:]
    return text
