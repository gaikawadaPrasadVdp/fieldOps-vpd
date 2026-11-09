const http = require('http');

http.get('http://localhost:8000/resources/', (res) => {
  let data = '';
  res.on('data', (chunk) => data += chunk);
  res.on('end', () => {
    console.log('Status code:', res.statusCode);
    console.log('Has fx-article-modal-trigger:', data.includes('fx-article-modal-trigger'));
    console.log('Has fx-article-modal-overlay:', data.includes('fx-article-modal-overlay'));
    console.log('Has fx-card-expand-link:', data.includes('fx-card-expand-link'));
    console.log('Has window.fxOpenArticleModal:', data.includes('fxOpenArticleModal'));

    // Check where read-more-link appears
    const lines = data.split('\n');
    lines.forEach((l, i) => {
      if (l.includes('fx-read-more-link')) {
        console.log(`Line ${i + 1}: ${l.trim()}`);
      }
    });
  });
}).on('error', (e) => {
  console.error('Error:', e.message);
});
