-- Trimmed-down sample covering time windows, timeouts, actions, and single-frame flags.
scenes = {
    sample_scene = {
        start_alive = {
            start_time = 100,
            end_time = 400,
            timeout = { when = 800, nextsequence = "fail" },
            actions = {
                { input = "left", from = 150, to = 300, interrupt = "jump", nextsequence = "success" },
                { input = "right", from = 200, to = 350, interrupt = "duck", nextsequence = "fail" },
            },
        },
        success = {
            start_time = 1200,
            end_time = 1300,
            is_single_frame = true,
        },
        fail = {
            start_time = 1600,
            end_time = 1700,
        },
    },
}
