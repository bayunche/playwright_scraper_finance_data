const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();

  // 打开同花顺涨跌温度计页面
  await page.goto('https://stock.10jqka.com.cn/wenduji/');

  // 等待指标块加载（可根据页面内容检查CSS选择器是否变化）
  await page.waitForSelector('.b-top .rise em');  // 上涨家数
  await page.waitForSelector('.b-top .fall em');  // 下跌家数
  await page.waitForSelector('.zt-list .zt em');  // 涨停家数
  await page.waitForSelector('.dt-list .dt em');  // 跌停家数

  // 抓取具体数据
  const data = await page.evaluate(() => {
    const getNum = (selector) => {
      const el = document.querySelector(selector);
      return el ? parseInt(el.textContent.replace(/,/g, '')) : null;
    };

    return {
      upCount: getNum('.b-top .rise em'),
      downCount: getNum('.b-top .fall em'),
      limitUpCount: getNum('.zt-list .zt em'),
      limitDownCount: getNum('.dt-list .dt em'),
    };
  });

  console.log(`📈 今日A股数据（同花顺）：`);
  console.log(` 上涨家数： ${data.upCount}`);
  console.log(` 下跌家数： ${data.downCount}`);
  console.log(` 涨停家数： ${data.limitUpCount}`);
  console.log(` 跌停家数： ${data.limitDownCount}`);

  await browser.close();
})();