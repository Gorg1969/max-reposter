# admin_templates.py
# ============================================================
# HTML-шаблоны админки
# ============================================================

BASE_STYLE = """
<style>
    body { font-family: Arial; max-width: 1400px; margin: 30px auto;
           padding: 20px; background: #f5f5f5; color: #333; }
    .card { background: white; padding: 20px; border-radius: 8px;
            margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    h1, h2 { margin-top: 0; }
    a { color: #007bff; text-decoration: none; }
    .btn { display: inline-block; padding: 10px 18px; background: #007bff;
           color: white; border-radius: 5px; text-decoration: none;
           margin-right: 8px; margin-bottom: 8px; border: none;
           cursor: pointer; font-size: 14px; }
    .btn-green { background: #28a745; }
    .btn-red { background: #dc3545; }
    .btn-orange { background: #fd7e14; }
    .btn-gray { background: #6c757d; }
    .btn:hover { opacity: 0.9; }
    .stats { display: flex; gap: 20px; flex-wrap: wrap; }
    .stat { background: #f8f9fa; padding: 15px 25px; border-radius: 5px; }
    .stat .num { font-size: 28px; font-weight: bold; color: #007bff; }
    .stat .num.green { color: #28a745; }
    .stat .num.red { color: #dc3545; }
    .stat .lbl { font-size: 13px; color: #666; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { padding: 10px; border-bottom: 1px solid #eee;
             text-align: left; font-size: 13px; vertical-align: top; }
    th { background: #f8f9fa; font-weight: bold; }
    tr:hover { background: #fafafa; }
    .badge { display: inline-block; padding: 3px 9px; border-radius: 12px;
             font-size: 11px; font-weight: bold; color: white; }
    .badge-ok { background: #28a745; }
    .badge-err { background: #dc3545; }
    .badge-pend { background: #fd7e14; }
    .badge-skip { background: #6c757d; }
    code { background: #f0f0f0; padding: 2px 6px;
           border-radius: 3px; font-size: 12px; }
    pre { background: #1e1e1e; color: #d4d4d4; padding: 15px;
          border-radius: 5px; overflow-x: auto; font-size: 12px;
          max-height: 500px; overflow-y: auto; white-space: pre-wrap;
          word-break: break-all; }
    .empty { text-align: center; color: #999; padding: 40px; }
    .preview { color: #555; font-size: 12px; max-width: 400px;
               overflow: hidden; text-overflow: ellipsis;
               white-space: nowrap; }
    .filters { margin: 15px 0; }
    .filters a { margin-right: 10px; padding: 6px 14px;
                 border-radius: 20px; background: #e9ecef;
                 color: #333; font-size: 13px; }
    .filters a.active { background: #007bff; color: white; }
</style>
"""


def admin_index_html(stats, recent, sources, target, triggers, blacklist_count):
    """Главная страница админки."""
    rows = ""
    for r in recent:
        status = r.get("status", "")
        badge = {
            "success": '<span class="badge badge-ok">✓ OK</span>',
            "error": '<span class="badge badge-err">✗ Ошибка</span>',
            "pending": '<span class="badge badge-pend">⏳</span>',
            "skipped": '<span class="badge badge-skip">⏭</span>',
        }.get(status, f'<span class="badge">{status}</span>')

        post_cell = (
            f'<a href="{r["target_post_link"]}" target="_blank">🔗 Пост</a>'
            if r.get("target_post_link") else "—"
        )
        err_cell = f'<span style="color:#dc3545">{r.get("error","")[:60]}</span>' if r.get("error") else ""

        rows += f"""
        <tr>
            <td>{r.get('id','')}</td>
            <td>{r.get('created_at','')}</td>
            <td><code>{r.get('source_chat_id','')}</code></td>
            <td>{badge}</td>
            <td class="preview">{r.get('text_preview','')[:120]}</td>
            <td>{r.get('media_count',0)}</td>
            <td>{post_cell}</td>
            <td>{err_cell}</td>
            <td>
                <a href="/admin/repost/{r.get('mid','')}" style="font-size:12px">👁️</a>
                <a href="/admin/blacklist/add/{r.get('mid','')}" style="font-size:12px;color:#dc3545"
                   onclick="return confirm('Добавить в чёрный список?')">🚫</a>
                <a href="/admin/delete/{r.get('mid','')}" style="font-size:12px;color:#dc3545"
                   onclick="return confirm('Удалить запись из истории?')">🗑️</a>
            </td>
        </tr>
        """

    if not rows:
        rows = '<tr><td colspan="9" class="empty">Пока нет пересылок</td></tr>'

    sources_html = "".join(f"<code>{c}</code> " for c in sorted(sources))
    triggers_html = "".join(f"<code>{t}</code><br>" for t in triggers)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="30">
        <title>max-reposter — админка</title>
        {BASE_STYLE}
    </head>
    <body>
        <div class="card">
            <h1>🤖 max-reposter — админка</h1>
            <p>Автообновление каждые 30 секунд.</p>
            <a href="/admin" class="btn">🔄 Обновить</a>
            <a href="/admin/settings" class="btn">⚙️ Настройки</a>
            <a href="/admin/blacklist" class="btn">🚫 Чёрный список ({blacklist_count})</a>
            <a href="/setup_webhook" class="btn btn-gray">🔗 Вебхук</a>
            <a href="/debug" class="btn btn-gray">🐛 Debug</a>
        </div>

        <div class="card">
            <h2>📊 Статистика</h2>
            <div class="stats">
                <div class="stat"><div class="lbl">Всего</div>
                    <div class="num">{stats['total']}</div></div>
                <div class="stat"><div class="lbl">Успешно</div>
                    <div class="num green">{stats['success']}</div></div>
                <div class="stat"><div class="lbl">Ошибок</div>
                    <div class="num red">{stats['errors']}</div></div>
                <div class="stat"><div class="lbl">Сегодня</div>
                    <div class="num">{stats['today']}</div></div>
            </div>
        </div>

        <div class="card">
            <h2>📋 Последние 100 пересылок</h2>
            <div class="filters">
                <a href="/admin" class="active">Все</a>
                <a href="/admin?status=success">✅ Успешные</a>
                <a href="/admin?status=error">❌ Ошибки</a>
            </div>
            <div style="overflow-x:auto">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th><th>Время</th><th>Откуда</th>
                            <th>Статус</th><th>Текст</th><th>Медиа</th>
                            <th>Пост</th><th>Ошибка</th><th>Действия</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        </div>

        <div class="card">
            <h2>📥 Группы-источники ({len(sources)})</h2>
            {sources_html}
        </div>

        <div class="card">
            <h2>📤 Целевой канал</h2>
            <code>{target}</code>
        </div>

        <div class="card">
            <h2>🔎 Фильтры</h2>
            {triggers_html}
        </div>
    </body>
    </html>
    """


def admin_repost_detail_html(r):
    """Детали одной пересылки."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Пересылка {r.get('mid','')}</title>
        {BASE_STYLE}
    </head>
    <body>
        <div class="card">
            <h1>👁️ Детали пересылки</h1>
            <a href="/admin" class="btn">← Назад</a>
            <a href="/admin/blacklist/add/{r.get('mid','')}" class="btn btn-red"
               onclick="return confirm('Добавить в чёрный список?')">🚫 В чёрный список</a>
        </div>
        <div class="card">
            <table>
                <tr><th>mid</th><td><code>{r.get('mid','')}</code></td></tr>
                <tr><th>Время</th><td>{r.get('created_at','')}</td></tr>
                <tr><th>Откуда (chat_id)</th><td><code>{r.get('source_chat_id','')}</code></td></tr>
                <tr><th>Куда (chat_id)</th><td><code>{r.get('target_chat_id','')}</code></td></tr>
                <tr><th>Статус</th><td>{r.get('status','')}</td></tr>
                <tr><th>Медиа</th><td>{r.get('media_count',0)}</td></tr>
                <tr><th>Ссылка на пост</th>
                    <td>{f'<a href="{r["target_post_link"]}" target="_blank">{r["target_post_link"]}</a>' if r.get('target_post_link') else '—'}</td></tr>
                <tr><th>Ошибка</th>
                    <td style="color:#dc3545">{r.get('error','') or '—'}</td></tr>
            </table>
        </div>
        <div class="card">
            <h2>📝 Превью текста</h2>
            <pre>{r.get('text_preview','')}</pre>
        </div>
    </body>
    </html>
    """


def admin_settings_html(sources, target, triggers, saved=False):
    """Страница настроек (только просмотр — редактирование в config.py)."""
    saved_msg = '<div style="background:#d4edda;padding:12px;border-radius:5px;margin-bottom:15px">✅ Сохранено</div>' if saved else ""
    sources_html = "".join(f"<code>{c}</code><br>" for c in sorted(sources))
    triggers_html = "".join(f"<code>{t}</code><br>" for t in triggers)
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Настройки</title>
        {BASE_STYLE}
    </head>
    <body>
        <div class="card">
            <h1>⚙️ Настройки</h1>
            <a href="/admin" class="btn">← Назад</a>
        </div>
        {saved_msg}
        <div class="card">
            <h2>📥 Группы-источники ({len(sources)})</h2>
            <p style="color:#666;font-size:13px">Редактируется в <code>config.py</code> → <code>SOURCE_CHAT_IDS</code></p>
            {sources_html}
        </div>
        <div class="card">
            <h2>📤 Целевой канал</h2>
            <p style="color:#666;font-size:13px">Редактируется в <code>config.py</code> → <code>TARGET_CHANNEL_ID</code></p>
            <code>{target}</code>
        </div>
        <div class="card">
            <h2>🔎 Фильтры по фразам</h2>
            <p style="color:#666;font-size:13px">Редактируется в <code>config.py</code> → <code>TRIGGER_PHRASES</code></p>
            {triggers_html}
        </div>
        <div class="card">
            <h2>🧹 Очистка истории</h2>
            <p>Удалить записи старше 90 дней:</p>
            <a href="/admin/cleanup_history" class="btn btn-red"
               onclick="return confirm('Удалить записи старше 90 дней?')">🧹 Очистить</a>
        </div>
    </body>
    </html>
    """


def admin_blacklist_html(items):
    rows = ""
    for it in items:
        rows += f"""
        <tr>
            <td><code>{it.get('mid','')}</code></td>
            <td>{it.get('reason','')}</td>
            <td>{it.get('created_at','')}</td>
            <td><a href="/admin/blacklist/remove/{it.get('mid','')}" class="btn btn-red"
                   style="padding:5px 10px;font-size:12px"
                   onclick="return confirm('Убрать из чёрного списка?')">🗑️</a></td>
        </tr>
        """
    if not rows:
        rows = '<tr><td colspan="4" class="empty">Чёрный список пуст</td></tr>'

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Чёрный список</title>
        {BASE_STYLE}
    </head>
    <body>
        <div class="card">
            <h1>🚫 Чёрный список</h1>
            <p>Сообщения из этого списка больше не будут пересылаться.</p>
            <a href="/admin" class="btn">← Назад</a>
        </div>
        <div class="card">
            <table>
                <thead><tr><th>mid</th><th>Причина</th><th>Добавлено</th><th></th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </body>
    </html>
    """
