use tauri::{
    menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem},
    tray::TrayIconBuilder,
    App, Emitter, Runtime,
};

pub fn create_tray<R: Runtime>(app: &App<R>) -> tauri::Result<()> {
    let brief = MenuItemBuilder::with_id("brief", "Dzisiejszy Brief").build(app)?;
    let new_chat = MenuItemBuilder::with_id("new_chat", "Nowy Chat").build(app)?;
    let voice = MenuItemBuilder::with_id("voice", "Asystent Głosowy").build(app)?;
    let status = MenuItemBuilder::with_id("status", "Status: łączenie...")
        .enabled(false)
        .build(app)?;
    let quit = MenuItemBuilder::with_id("quit", "Zamknij").build(app)?;

    let menu = MenuBuilder::new(app)
        .item(&brief)
        .item(&new_chat)
        .item(&voice)
        .separator()
        .item(&status)
        .separator()
        .item(&quit)
        .build()?;

    TrayIconBuilder::new()
        .menu(&menu)
        .tooltip("Gilbertus Albans")
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
