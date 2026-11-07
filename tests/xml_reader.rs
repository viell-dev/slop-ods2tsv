use std::io::Cursor;
use xml::reader::{ParserConfig, XmlEvent};

fn parse(bytes: &[u8]) -> Result<String, xml::reader::Error> {
    let reader = ParserConfig::new()
        .allow_multiple_root_elements(false)
        .whitespace_to_characters(true)
        .cdata_to_characters(true)
        .create_reader(Cursor::new(bytes));
    let mut text = String::new();
    for event in reader {
        if let XmlEvent::Characters(value) = event? {
            text.push_str(&value);
        }
    }
    Ok(text)
}

#[test]
fn dependency_handles_encodings_entities_and_complete_document() {
    assert_eq!(parse(b"<r>A&amp;&#xE9;<![CDATA[Z]]></r>").unwrap(), "A&éZ");
    let latin1 = b"<?xml version='1.0' encoding='ISO-8859-1'?><r>caf\xe9</r>";
    assert_eq!(parse(latin1).unwrap(), "café");
    let long = format!(
        "<?xml version='1.0'{}encoding='ISO-8859-1'?><r>caf",
        " ".repeat(100)
    );
    let mut bytes = long.into_bytes();
    bytes.extend_from_slice(b"\xe9</r>");
    assert_eq!(parse(&bytes).unwrap(), "café");
    for little in [true, false] {
        let mut bytes = if little {
            vec![0xff, 0xfe]
        } else {
            vec![0xfe, 0xff]
        };
        for unit in "<?xml version='1.0' encoding='UTF-16'?><r>café</r>".encode_utf16() {
            bytes.extend_from_slice(&if little {
                unit.to_le_bytes()
            } else {
                unit.to_be_bytes()
            });
        }
        assert_eq!(parse(&bytes).unwrap(), "café");
    }
    assert!(parse(b"<r><sheet>Data</sheet>").is_err());
    assert!(parse(b"<r>Data</r><extra/>").is_err());
    assert!(parse(b"<r>&unknown;</r>").is_err());
}
