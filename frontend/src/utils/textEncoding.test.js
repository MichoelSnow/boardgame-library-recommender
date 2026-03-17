import { decodeGameDescription, repairMojibake } from './textEncoding';

describe('text encoding helpers', () => {
  test('decodeGameDescription decodes HTML entities and preserves line breaks', () => {
    const result = decodeGameDescription('Tom &amp; Jerry&#10;Line 2');
    expect(result).toBe('Tom & Jerry\nLine 2');
  });

  test('repairMojibake fixes common UTF-8 mojibake sequences', () => {
    expect(repairMojibake('FranÃ§ais')).toBe('Français');
    expect(repairMojibake('Itâ€™s great')).toBe('It’s great');
  });

  test('repairMojibake fixes mojibake Japanese text', () => {
    const mojibake = 'æŒ‡è¼ªã‚’è½ã¨ã•ãªã„ã§';
    expect(repairMojibake(mojibake)).toBe('指輪を落とさないで');
  });

  test('repairMojibake fixes mojibake fragments inside mixed text', () => {
    const mixed =
      'Before the King in Yellow Cometh (é»„è¡£ã®çŽ‹ãŒã‚„ã£ã¦ãã‚‹å‰ã«)';
    expect(repairMojibake(mixed)).toBe(
      'Before the King in Yellow Cometh (黄衣の王がやってくる前に)'
    );
  });

  test('repairMojibake repairs mojibake chunk next to valid CJK text', () => {
    const mixedChunk = 'é€™æ˜¯測試';
    expect(repairMojibake(mixedChunk)).toBe('這是測試');
  });

  test('repairMojibake handles mojibake with normal punctuation elsewhere in sentence', () => {
    const withEmDash =
      '—description from the publisher (translated) "é­”æ³•å°‘å¥³ã¾ã©ã‹â˜†ãƒžã‚®ã‚«"';
    expect(repairMojibake(withEmDash)).toContain('魔法少女まどか☆マギカ');
  });

  test('repairMojibake fixes long mixed zh paragraph with truncated token', () => {
    const broken =
      'é€™æ˜¯ä¸€å€‹ä»¥2011å¹´1æœˆåœ¨æ—¥æœ¬æ’­æ”¾çš„å‹•ç•«"é­”æ³•å°‘å¥³ã¾ã©ã‹â˜†ãƒžã‚®ã‚«"ç‚ºåŸºæœ¬æ¦‚å¿µè¨­è¨ˆçš„éŠæˆ²ã€‚åœ¨é€™å€‹éŠæˆ²ä¸­ä½ æ˜¯ä¸€ä½é­”æ³•å°‘å¥³ï¼Œå…±åŒèˆ‡ä¸–ç•Œä¸Šçš„ç½ªæƒ¡æ ¹æºï¼Œä¹Ÿå°±æ˜¯é‚ªæƒ¡çš„é­”å¥³é€²è¡Œæˆ°é¬¥ã€‚ä½†æ˜¯åœ¨æˆ°é¬¥çš„éŽç¨‹ä¸­é­”æ³•å°‘å¥³å€‘æœƒå—ä¸äº†ç²¾ç¥žçš„æŠ˜ç£¨ï¼Œç²¾ç¥žçš„å‰µå‚·ï¼Œèº«å¿ƒæ¼¸æ¼¸è®Šå¾—æ±¡ç©¢ä¸å ªï¼Œè€Œè®Šæˆé­”æ³•å°‘å¥³å€‘æœ€å¤§çš„æ•µäºº--é­”å¥³ï¼Œåœ¨ç“¦çˆ¾æ™®é­¯å‰æ€å¤œåˆ°ä¾†çš„æ—¥å­ä¸æ–·è¿«è¿‘ä¹‹ä¸‹ï¼Œé­”æ³•å°‘å¥³å€‘çš„åŒä¼´ä¹Ÿä¸€å€‹ä¸€å€‹çš„æ¸›å°‘ï¼Œè€Œæœ€çµ‚åˆ°åº•æ˜¯å‰©ä¸‹çš„é­”æ³•å°‘å¥³å€‘èƒ½å¤ 成功擊倒魔女之夜，還是魔女們最終可以吞噬所有魔法少女的靈魂呢？';

    const repaired = decodeGameDescription(broken);
    expect(repaired).toContain('這是一個以2011年1月在日本播放的動畫"魔法少女まどか☆マギカ"');
    expect(repaired).toContain('成功擊倒魔女之夜');
  });

  test('repairMojibake leaves valid text untouched', () => {
    expect(repairMojibake('Already valid UTF-8: Français')).toBe(
      'Already valid UTF-8: Français'
    );
  });
});
