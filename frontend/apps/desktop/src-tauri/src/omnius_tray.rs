use tauri::{
    menu::{MenuBuilder, MenuItemBuilder},
    tray::TrayIconBuilder,
    App, Emitter, Runtime,
};

pub fn create_tray<R: Runtime>(app: &App<R>) -> tauri::Result<()> {
    let ask = MenuItemBuilder::with_id("ask", "Zapytaj Omniusa").build(app)?;
    let plugins = MenuItemBuilder::with_id("plugins", "Wtyczki").build(app)?;
    let status = MenuItemBuilder::with_id("status", "Status: \u{0142}\u{0105}czenie...")
        .enabled(false)
        .build(app)?;
    let settings = MenuItemBuilder::with_id("settings", "Ustawienia").build(app)?;
    let quit = MenuItemBuilder::with_id("quit", "Zamknij").build(app)?;

    let menu = MenuBuilder::new(app)
        .item(&ask)
        .item(&plugins)
        .separator()
        .item(&status)
        .separator()
        .item(&settings)
        .item(&quit)
        .build()?;

    TrayIconBuilder::new()
        .menu(&menu)
        .tooltip("Omnius")
        .on_menu_event(move |app_handle, event| {
            let id = event.id().as_ref();
            match id {
                "quit" => {
                    app_handle.exit(0);
                }
                action => {
                    let _ = app_handle.emit("tray-action", action.to_string());
                }
            }
        })
        .build(app)?;

    Ok(())
}
