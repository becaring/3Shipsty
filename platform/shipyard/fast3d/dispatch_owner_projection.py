"""Bind the pinned modern interpreter's command walk to the Shipyard owner pin."""

from prepare_configuration import once


def transform(text):
    text = '#include "fast3d/dispatch_owner.h"\n' + text
    text = once(text, 'static std::weak_ptr<Interpreter> mInstance;', '''static std::weak_ptr<Interpreter> mInstance;
typedef Shipyard::Fast3D::DispatchOwner<Interpreter> XboxDispatchOwner;
static __declspec(thread) XboxDispatchOwner* sXboxDispatchOwner = 0;
static __forceinline Interpreter* XboxDispatchInterpreter() {
    if (sXboxDispatchOwner) return sXboxDispatchOwner->Get(mInstance);
    return XboxDispatchOwner::TemporaryBorrow(mInstance);
}''')
    text = once(text, '    mInstance = gfx;', '''    mInstance = gfx;
    XboxDispatchOwner::Invalidate(sXboxDispatchOwner);''')
    anchor = 'Interpreter* gfx = mInstance.lock().get();'
    if text.count(anchor) != 84:
        raise ValueError('Modern Fast3D handler ownership inventory changed')
    text = text.replace(anchor, 'Interpreter* gfx = XboxDispatchInterpreter();')
    if text.count('mInstance.lock().get()') != 2:
        raise ValueError('Modern Fast3D non-handler ownership inventory changed')
    text = once(text, '    g_exec_stack.start((F3DGfx*)commands);', '''    {
    XboxDispatchOwner dispatchOwner(sXboxDispatchOwner, mInstance);
    g_exec_stack.start((F3DGfx*)commands);''')
    text = once(text, '        gfx_step();\n    }\n\n    Flush();', '''        gfx_step();
    }
    }

    Flush();''')
    return text
