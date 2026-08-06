#include "PluginEditor.h"
#include <algorithm>
#include <array>
#include <vector>

AmenDrummerEditor::AmenDrummerEditor(AmenDrummerProcessor& p)
    : AudioProcessorEditor(&p), processor(p)
{
    setSize(320, 340);
    startTimerHz(60);
}

void AmenDrummerEditor::timerCallback()
{
    pollForNewOnsets();
    repaint();
}

void AmenDrummerEditor::pollForNewOnsets()
{
    const juce::uint32 kickMs = processor.kick.lastOnsetMs.load();
    const juce::uint32 snareMs = processor.snare.lastOnsetMs.load();
    const juce::uint32 cymbalMs = processor.cymbal.lastOnsetMs.load();

    // Collect whichever bands fired a new onset since the last poll, then
    // feed them to the sprite in chronological order (multiple bands can
    // trigger within one ~16ms GUI tick on a dense break).
    std::array<std::pair<juce::String, juce::uint32>, 3> candidates {
        std::make_pair(juce::String("kick"), kickMs),
        std::make_pair(juce::String("snare"), snareMs),
        std::make_pair(juce::String("cymbal"), cymbalMs),
    };

    std::array<juce::uint32*, 3> lastSeen { &lastSeenKickMs, &lastSeenSnareMs, &lastSeenCymbalMs };

    std::vector<std::pair<juce::String, juce::uint32>> newOnsets;
    for (size_t i = 0; i < candidates.size(); ++i)
    {
        if (candidates[i].second != 0 && candidates[i].second != *lastSeen[i])
        {
            newOnsets.push_back(candidates[i]);
            *lastSeen[i] = candidates[i].second;
        }
    }

    std::sort(newOnsets.begin(), newOnsets.end(),
              [](const auto& a, const auto& b) { return a.second < b.second; });

    for (auto& onset : newOnsets)
        sprite.trigger(onset.first, onset.second);
}

void AmenDrummerEditor::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colours::black);

    auto bounds = getLocalBounds();
    auto footer = bounds.removeFromBottom(24);

    const auto nowMs = juce::Time::getMillisecondCounter();
    const auto& frame = sprite.getFrame(nowMs);

    if (frame.isValid())
    {
        auto imageBounds = bounds.reduced(10).toFloat();
        const float scale = juce::jmin(imageBounds.getWidth() / (float)frame.getWidth(),
                                        imageBounds.getHeight() / (float)frame.getHeight());
        const float w = frame.getWidth() * scale;
        const float h = frame.getHeight() * scale;
        juce::Rectangle<float> dest(0, 0, w, h);
        dest.setCentre(imageBounds.getCentre());
        g.drawImage(frame, dest);
    }

    g.setColour(juce::Colours::grey);
    g.setFont(12.0f);
    juce::String footerText;
    footerText << "blocks: " << (int)processor.debugBlockCount.load()
               << "  ch: " << processor.debugNumChannels.load()
               << "  smp/blk: " << processor.debugNumSamples.load();
    g.drawText(footerText, footer, juce::Justification::centredLeft);
}
