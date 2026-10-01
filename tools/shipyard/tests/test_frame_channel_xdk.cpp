#include "application/frame_channel.h"
#include <vector>

struct Packet { std::vector<int> commands; };
static void action() {}

void frame_channel_xdk_contract() {
    ModernOverlap::FrameChannel<Packet> channel;
    ModernOverlap::FrameChannel<Packet>::Ticket ticket;
    Packet* build = NULL;
    const Packet* render = NULL;
    channel.acquireBuild(ticket, build);
    channel.deferRelease(ticket.generation, action);
    channel.queueIdleAction(action);
    channel.publish(ticket);
    channel.tryAcquireReady(ticket, render);
    channel.retire(ticket);
    channel.collectRetired();
    channel.acquireReady(ticket, render);
    channel.cancelBuild(ticket);
    channel.stopFeeder();
    channel.waitDrained();
    channel.resumeFeeder();
    channel.runOnRender(action);
    channel.pumpRenderJobs();
    channel.finishProducer();
    channel.requestStop();
    channel.isDrained();
    channel.waitRetired(ticket.generation);
    ModernOverlap::AudioGenerationGate audio;
    audio.begin(1);
    audio.complete(1);
    audio.wait(1);
    audio.requestStop();
}
