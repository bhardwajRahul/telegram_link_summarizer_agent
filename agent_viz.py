

import marimo

__generated_with = "0.13.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import nest_asyncio

    nest_asyncio.apply()  # Allow nested asyncio loops

    # --- The rest of your imports ---
    from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles
    from agent import build_graph  # Your import
    # ---------------------------------

    app = build_graph()

    # Now this should work without the RuntimeError
    png_bytes = app.get_graph().draw_mermaid_png(
        draw_method=MermaidDrawMethod.PYPPETEER,
    )

    # Display the image using marimo
    mo.image(src=png_bytes, alt="LangGraph Flow", caption="Telegram Summarizer Bot Graph")
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
