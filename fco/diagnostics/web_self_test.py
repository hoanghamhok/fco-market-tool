"""Exercise the packaged WebView2 UI and bridge without touching the game."""

import json
from pathlib import Path
import threading
import time
import traceback


def run_web_self_test(root, snapshot=None):
    import webview
    from fco.web_app import create_window

    window, api = create_window(root=root, hidden=True, updates=False)
    if snapshot:
        api._snapshot(snapshot)
    result = {}

    def check():
        try:
            if not window.events.loaded.wait(25):
                raise RuntimeError("WebView2 did not load the local interface")
            deadline = time.monotonic() + 20
            while window.evaluate_js("document.documentElement.dataset.ready") != "true":
                if time.monotonic() > deadline:
                    raise RuntimeError("UI bridge initialization timed out")
                time.sleep(0.1)
            script = r"""(async()=>{
                const assert=(condition,message)=>{if(!condition)throw new Error(message)};
                const click=selector=>document.querySelector(selector).click();
                const set=(id,value)=>{const el=document.getElementById(id);el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));};
                click('[data-page="salary"]');
                assert(document.querySelectorAll('.player-input').length===11,'11 salary inputs');
                document.querySelectorAll('.player-input').forEach(el=>set(el.id,'25'));
                assert(document.getElementById('salary-total').textContent==='275','salary sum');
                set('salary-ST','-1');
                assert(document.getElementById('salary-total').textContent==='275','reject negative salary');
                click('[data-formation="4-1-4-1"]');
                assert(document.getElementById('salary-total').textContent==='0','independent formations');
                assert(document.querySelectorAll('.player-input').length===11,'11 second formation inputs');
                set('salary-ST','30');set('salary-GK','18');
                assert(document.getElementById('salary-total').textContent==='48','second formation total');
                click('#clear-salary');assert(document.getElementById('salary-total').textContent==='0','clear');
                click('#undo-salary');assert(document.getElementById('salary-total').textContent==='48','undo');
                click('[data-formation="4-3-3"]');
                assert(document.getElementById('salary-total').textContent==='275','formation retained');
                click('[data-page="tax"]');set('tax-price','7.600.000.000.000');
                click('[data-member="svip"]');click('[data-coupon="30"]');await writeQueue;
                await new Promise(r=>setTimeout(r,100));
                assert(document.getElementById('tax-net').textContent==='6.384.000.000.000','tax integer precision');
                set('tax-price','invalid');await writeQueue;await new Promise(r=>setTimeout(r,100));
                assert(document.getElementById('tax-net').textContent==='—','invalid price clears stale total');
                set('tax-price','7.600.000.000.000');await writeQueue;
                click('[data-page="watch"]');
                assert(!document.getElementById('watch-dry').disabled && document.getElementById('watch-dry').checked,'dry run default');
                set('watch-limit','1234567890');
                assert(document.getElementById('watch-limit').value==='1.234.567.890','live BP grouping');
                click('[data-limit-value="10000000000"]');
                assert(document.getElementById('watch-limit').value==='10.000.000.000','quick value');
                assert(document.querySelector('[data-limit-value="10000000000"]').getAttribute('aria-pressed')==='true','quick value selected');
                set('watch-limit','800000000');set('watch-duration','180');await writeQueue;
                assert((await api.bootstrap()).watch.limit==='800.000.000','grouped BP persisted');
                click('[data-page="salary"]');await writeQueue;
                const oldEnabled=data.updates_enabled,oldInstall=data.update_install_supported;
                data.updates_enabled=true;data.update_install_supported=true;
                renderUpdate({status:'available',version:'99.0.0',notes:'<img src=x onerror=alert(1)>'});
                assert(!document.getElementById('update-panel').hidden,'update notification');
                assert(document.getElementById('update-notes').textContent.includes('<img'),'release notes rendered as text');
                assert(!document.querySelector('#update-notes img'),'release notes never execute HTML');
                const state=await api.get_state();
                renderState({...state,update:{status:'downloading',progress:50,version:'99.0.0'}});
                assert(document.getElementById('detect').disabled,'no game actions while downloading');
                assert(document.getElementById('update-progress').value===50,'update progress');
                renderState({...state,update:{status:'downloaded',version:'99.0.0'}});
                assert(!document.getElementById('detect').disabled,'game actions restored after download');
                assert(document.getElementById('apply-update').textContent.includes('Khởi động lại'),'restart update button');
                data.updates_enabled=oldEnabled;data.update_install_supported=oldInstall;
                renderState(state);
                return {salary_total:275,second_total:48,tax_net:'6384000000000',pages:3,clear_undo:true,bridge:true,update_ui:true};
            })()"""
            completed = threading.Event()

            def capture(value):
                result["ui"] = value
                completed.set()

            window.evaluate_js(script, callback=capture)
            if not completed.wait(25):
                raise RuntimeError("UI interaction tests timed out")
            if not isinstance(result.get("ui"), dict) or result["ui"].get("salary_total") != 275:
                raise RuntimeError(f'UI interaction failure: {result.get("ui")}')
            for width, height in [(1200, 860), (980, 720)]:
                window.resize(width, height)
                time.sleep(0.15)
                for page in ("salary", "tax", "watch"):
                    bounds = window.evaluate_js("""(()=>{
                        showPage('%s',false);
                        renderUpdate({status:'available',version:'99.0.0',notes:'Nội dung bản mới để kiểm tra bố cục.'});
                        const main=document.querySelector('main');
                        return {overflow:main.scrollWidth>main.clientWidth+1,
                            page:document.documentElement.scrollWidth>innerWidth+1,
                            samples:[...document.querySelectorAll('.limit-example-grid button')]
                                .some(button=>button.scrollWidth>button.clientWidth+1)};
                    })()""" % page)
                    assert not bounds["overflow"] and not bounds["page"] and not bounds["samples"], (
                        width,
                        height,
                        page,
                        bounds,
                    )
            saved = json.loads((Path(root) / "salary-settings.json").read_text(encoding="utf-8"))
            assert saved["squads"]["4-3-3"]["ST"] == "25"
            assert saved["squads"]["4-1-4-1"]["GK"] == "18"
            assert api.bootstrap()["watch"]["reset_duration"] == "180"
            api._set(busy=True)
            window.evaluate_js("renderState(" + json.dumps(api.get_state()) + ")")
            assert window.evaluate_js(
                "document.getElementById('start-watch').disabled && document.querySelector('[data-page=salary]').disabled"
            )
            assert window.evaluate_js(
                "[...document.querySelectorAll('[data-limit-value]')].every(button=>button.disabled)"
            )
            api._set(busy=False)
            result["engine"] = "WebView2"
            result["sizes"] = ["1200x860", "980x720"]
            # An immediate native close must flush the last edit through the bridge.
            window.evaluate_js(
                "showPage('salary',false); const last=document.getElementById('salary-ST'); last.value='26'; last.dispatchEvent(new Event('input',{bubbles:true}));"
            )
            result["ok"] = True
        except Exception:
            result["ok"] = False
            result["error"] = traceback.format_exc()
        finally:
            if not result.get("ok"):
                api._close_ready = True
            api._set(busy=False)
            window.destroy()

    webview.start(check, gui="edgechromium", storage_path=str(Path(root) / "webview"))
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "WebView self-test did not complete"))
    final = json.loads((Path(root) / "salary-settings.json").read_text(encoding="utf-8"))
    assert final["squads"]["4-3-3"]["ST"] == "26", "Closing must flush pending input"
    result["close_flush"] = True
    return result
