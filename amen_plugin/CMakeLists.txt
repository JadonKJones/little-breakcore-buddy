cmake_minimum_required(VERSION 3.22)

project(AmenDrummer VERSION 0.0.1)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(ANIMATION_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../animation frames")

include(FetchContent)
FetchContent_Declare(
    JUCE
    GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
    GIT_TAG 7.0.12
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(JUCE)

juce_add_plugin(AmenDrummer
    COMPANY_NAME "sakamotosan"
    PLUGIN_MANUFACTURER_CODE Skmt
    PLUGIN_CODE Adr1
    FORMATS VST3
    PRODUCT_NAME "Drummer"
    IS_SYNTH FALSE
    NEEDS_MIDI_INPUT FALSE
    NEEDS_MIDI_OUTPUT FALSE
    IS_MIDI_EFFECT FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS FALSE
    VST3_CATEGORIES "Fx" "Visualizer"
)

juce_add_binary_data(AmenDrummerAssets
    SOURCES
        "${ANIMATION_DIR}/idle.png"
        "${ANIMATION_DIR}/idlek.png"
        "${ANIMATION_DIR}/snare1.png"
        "${ANIMATION_DIR}/snare2.png"
        "${ANIMATION_DIR}/snare3.png"
        "${ANIMATION_DIR}/snare4.png"
        "${ANIMATION_DIR}/snare5.png"
        "${ANIMATION_DIR}/snare6.png"
        "${ANIMATION_DIR}/snare1k.png"
        "${ANIMATION_DIR}/snare2k.png"
        "${ANIMATION_DIR}/snare3k.png"
        "${ANIMATION_DIR}/snare4k.png"
        "${ANIMATION_DIR}/snare5k.png"
        "${ANIMATION_DIR}/snare6k.png"
        "${ANIMATION_DIR}/crash1.png"
        "${ANIMATION_DIR}/crash2.png"
        "${ANIMATION_DIR}/crash3.png"
        "${ANIMATION_DIR}/crash4.png"
        "${ANIMATION_DIR}/crash1k.png"
        "${ANIMATION_DIR}/crash2k.png"
        "${ANIMATION_DIR}/crash3k.png"
        "${ANIMATION_DIR}/crash4k.png"
)

target_sources(AmenDrummer
    PRIVATE
        Source/PluginProcessor.cpp
        Source/PluginEditor.cpp
)

target_compile_definitions(AmenDrummer
    PUBLIC
        JUCE_WEB_BROWSER=0
        JUCE_USE_CURL=0
        JUCE_VST3_CAN_REPLACE_VST2=0
)

target_link_libraries(AmenDrummer
    PRIVATE
        juce::juce_audio_utils
        juce::juce_dsp
        AmenDrummerAssets
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags
)
