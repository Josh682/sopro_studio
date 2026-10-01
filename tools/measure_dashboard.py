import sys
import os
import json
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView

def main():
    app = QApplication(sys.argv)
    
    html_path = os.path.abspath("reference/dashboard_grid.html")
    if not os.path.exists(html_path):
        print(f"Error: {html_path} does not exist")
        sys.exit(1)
        
    print("Initializing QWebEngineView...")
    view = QWebEngineView()
    view.resize(1120, 720)
    view.show()
    print("Loading URL...")
    
    results = {}

    def on_loaded(ok):
        if not ok:
            print("Failed to load page")
            app.quit()
            return
            
        js_code = """
        (() => {
            const cards = Array.from(document.querySelectorAll('.card'));
            const cardMeasurements = cards.map((c, i) => {
                const mod = c.getAttribute('data-module') || ('MOD-0' + (i+1));
                const title = c.querySelector('.card-title')?.textContent?.trim() || '';
                return {
                    index: i + 1,
                    module: mod,
                    title: title,
                    clientWidth: c.clientWidth,
                    clientHeight: c.clientHeight,
                    scrollWidth: c.scrollWidth,
                    scrollHeight: c.scrollHeight,
                    offsetHeight: c.offsetHeight,
                    diff: c.scrollHeight - c.clientHeight,
                    overflow: c.scrollHeight > c.clientHeight
                };
            });

            const doc = document.documentElement;
            const body = document.body;
            const viewportInfo = {
                windowInnerWidth: window.innerWidth,
                windowInnerHeight: window.innerHeight,
                docClientWidth: doc.clientWidth,
                docClientHeight: doc.clientHeight,
                docScrollWidth: doc.scrollWidth,
                docScrollHeight: doc.scrollHeight,
                bodyScrollHeight: body.scrollHeight,
                hasHorizontalScroll: doc.scrollWidth > doc.clientWidth,
                hasVerticalScroll: doc.scrollHeight > doc.clientHeight
            };

            return { cardMeasurements, viewportInfo };
        })()
        """
        
        def handle_eval_result(res):
            print("MEASUREMENT_START")
            print(json.dumps(res, indent=2))
            print("MEASUREMENT_END")
            app.quit()

        # Give layout a tiny moment to stabilize
        QTimer.singleShot(200, lambda: view.page().runJavaScript(js_code, handle_eval_result))

    view.loadFinished.connect(on_loaded)
    view.load(QUrl.fromLocalFile(html_path))
    
    # Timeout after 5 seconds
    QTimer.singleShot(5000, lambda: (print("Timeout waiting for page load"), app.quit()))
    
    app.exec()

if __name__ == "__main__":
    main()
