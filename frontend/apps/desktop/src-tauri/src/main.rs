mod commands;
mod tray;

use tauri::Emitter;
use tauri_plugin_deep_link::DeepLinkExt;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            tray::create_tray(app)?;

            #[cfg(any(target_os = "linux", all(debug_assertions, target_os = "windows")))]
            {
                app.deep_link().register("gilbertus")?;
            }

            let handle = app.handle().clone();
            app.deep_link().on_open_url(move |urls| {
                if let Some(url) = urls.first() {
                    let _ = handle.emit("deep-link", url.to_string());
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::get_platform,
            commands::get_version,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
