# Actual object-extension registry

`prepare_object_extension.py --build` generates all three complete modern units:
ObjectExtension, ActorListIndex and ActorMaximumHealth. All compile with XDK.
Registry IDs, object/type keys, hook registrations and payload behavior remain
the upstream implementation.

Shipyard owns the reached standard-library compatibility boundary (B): copyable
owned values with exact RTTI and nonthrowing pointer casts. `any.h` implements
that subset; it does not claim the full std::any API. Copy clones the stored
value, failed copies leave the target unchanged, move transfers ownership,
and forwarding constructors exclude any itself. Const and array/literal decay
are covered. RTTI must remain enabled. There is currently one heap allocation
per stored value, without small-object optimization; profile this boundary once
actual gameplay works.

Other A/B adaptations are constructor defaults, constant InvalidId, hash spelling,
contains-to-find and the existing erase_if predicate expanded into an iterator
erase loop. The registry and actor feature bodies retain ownership of all state.
Runtime native values receive no endian conversion.

`test_object_extension.py` compares original std::any with the owned implementation,
then the complete original/projected registry: IDs, null objects, object isolation,
mutable payload access, removal, captured ownership, failed copies and destruction.
Native contracts and all three production units compile. No game hook execution,
Xenia validation or performance claim is made.
