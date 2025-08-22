XPATHS = {
    "login": {
        "pane_side": '//div[@id="pane-side"]',
        "qr_code": '//canvas',
        "progress_page": '//progress'
    },
    "chat": {
        "input_box": '//div[@role="textbox" and @contenteditable="true" and @aria-label="Type a message"]',
        "invalid_number": '//div[contains(text(), "not on WhatsApp")]',
    },
    "attachment": {
        "attach_button": '//button[@title="Attach" and @type="button"]',
        "file_input": '//input[@accept="*"]',
        "send_button": "//div[@role='button' and @aria-label='Send']",
        "caption_box": '//div[@role="textbox" and @contenteditable="true" and @aria-label="Add a caption"]',
        "close_button": '//div[@role="button" and @aria-label="Close"]'
    }
}
PANE_SIDE_ID = "pane-side"
PANE_SIDE_XPATH = XPATHS["login"]["pane_side"]
QR_CODE_XPATH = XPATHS["login"]["qr_code"]
PROGRESS_PAGE_XPATH = XPATHS["login"]["progress_page"]
CHAT_INPUT_BOX_XPATH = XPATHS["chat"]["input_box"]
CHAT_INVALID_NUMBER_XPATH = XPATHS["chat"]["invalid_number"]
ATTACH_BUTTON_XPATH = XPATHS["attachment"]["attach_button"]
FILE_INPUT_XPATH = XPATHS["attachment"]["file_input"]
SEND_BUTTON_XPATH = XPATHS["attachment"]["send_button"]
CAPTION_BOX_XPATH = XPATHS["attachment"]["caption_box"]
CLOSE_BUTTON_XPATH = XPATHS["attachment"]["close_button"]

