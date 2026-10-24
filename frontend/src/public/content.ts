export type Language = 'en' | 'ur';

type Program = { title: string; body: string };
type HomeContent = {
  title: string; description: string; skip: string; brand: string; staff: string;
  openMenu: string; closeMenu: string; navigation: { id: string; label: string }[];
  hero: { title: string; body: string; action: string; secondary: string; note: string };
  about: { title: string; paragraphs: string[]; closing: string };
  programs: { title: string; intro: string; items: Program[] };
  branches: { title: string; body: string; empty: string; action: string };
  events: { title: string; body: string; emptyTitle: string; empty: string };
  join: { title: string; body: string; steps: { title: string; body: string }[]; notice: string; staffPrompt: string };
  contact: { title: string; body: string; empty: string; explore: string; staffTitle: string; staffBody: string };
  footer: { note: string; top: string };
};

export const content: Record<Language, HomeContent> = {
  en: {
    title: 'Branch Office | Good starts close to home',
    description: 'Meet Branch Office: local branches, volunteers and head office working together for their communities.',
    skip: 'Skip to content', brand: 'Branch Office', staff: 'Staff sign-in', openMenu: 'Open menu', closeMenu: 'Close menu',
    navigation: [
      { id: 'home', label: 'Home' }, { id: 'about', label: 'About' }, { id: 'programs', label: 'Programs' },
      { id: 'branches', label: 'Branches' }, { id: 'events', label: 'Events' }, { id: 'join', label: 'Get Involved' }, { id: 'contact', label: 'Contact' },
    ],
    hero: {
      title: 'Good starts close to home',
      body: 'We bring local branches and volunteers together to turn shared purpose into community action.',
      action: 'Get involved', secondary: 'Discover our work', note: 'Local people. A shared purpose.',
    },
    about: {
      title: 'Built around people',
      paragraphs: [
        'Every community has people ready to help. Branch Office gives that willingness a place to belong, connecting local volunteers with branches and head office.',
        'Branches coordinate local work. Volunteers bring their time and skills. Head office supports the network and keeps shared work accountable.',
      ],
      closing: 'A local connection. A collective effort.',
    },
    programs: {
      title: 'Make your time count',
      intro: 'Give your time, share a skill or help a local team. Explore the programs and events across our branch network to find your starting point.',
      items: [
        { title: 'Give your time', body: 'Join local activities and work alongside a volunteer team. Published opportunities will explain what is needed and how to take part.' },
        { title: 'Share your skills', body: 'Bring your practical experience, ideas or organisational skills to a local team. The right opportunity starts with understanding where you can help.' },
        { title: 'Support local work', body: 'Help a branch organise its activities and keep local efforts moving. This website does not collect online payments.' },
      ],
    },
    branches: {
      title: 'A local connection',
      body: 'Our branches are where community work takes shape. They connect people nearby, coordinate volunteers and share progress with head office.',
      empty: 'Branch locations and local contacts will appear here when the directory is published.',
      action: 'How to take part',
    },
    events: {
      title: 'Make room for community',
      body: 'Meet the people behind local work. This is where you’ll find upcoming activities and opportunities to take part.',
      emptyTitle: 'No events published yet', empty: 'Check back for dates, locations and participation details as new events are announced.',
    },
    join: {
      title: 'Your time matters',
      body: 'You don’t need a staff account to take the first step. Choose a branch, share your interests and tell us when you can help.',
      steps: [
        { title: 'Find your branch', body: 'Explore published branch information and find a local team.' },
        { title: 'Tell us about yourself', body: 'Complete the volunteer application with your interests and details.' },
        { title: 'Meet your team', body: 'The HR team reviews applications and helps accepted volunteers take the next step.' },
      ],
      notice: 'Volunteer applications are not open yet. Please check back for published opportunities.', staffPrompt: 'Already part of the staff team?',
    },
    contact: {
      title: 'Keep in touch', body: 'Local questions deserve a local conversation. Send a message about a branch, a program or an idea you would like to share.',
      empty: 'Contact details have not been published yet.', explore: 'Explore', staffTitle: 'For our staff',
      staffBody: 'Access your workspace using the credentials provided by your Super Admin.',
    },
    footer: { note: 'People. Programmes. Progress.', top: 'Back to top' },
  },
  ur: {
    title: 'برانچ آفس | بھلائی کا آغاز اپنے محلے سے',
    description: 'برانچ آفس میں مقامی شاخیں، رضاکار اور مرکزی دفتر اپنی برادریوں کے لیے مل کر کام کرتے ہیں۔',
    skip: 'اصل مواد پر جائیں', brand: 'برانچ آفس', staff: 'عملے کا لاگ اِن', openMenu: 'مینو کھولیں', closeMenu: 'مینو بند کریں',
    navigation: [
      { id: 'home', label: 'صفحۂ اول' }, { id: 'about', label: 'تعارف' }, { id: 'programs', label: 'پروگرام' },
      { id: 'branches', label: 'شاخیں' }, { id: 'events', label: 'تقریبات' }, { id: 'join', label: 'شامل ہوں' }, { id: 'contact', label: 'رابطہ' },
    ],
    hero: {
      title: 'بھلائی کا آغاز اپنے محلے سے',
      body: 'ہم مقامی شاخوں اور رضاکاروں کو جوڑتے ہیں تاکہ مشترکہ مقصد، برادری کی خدمت کا ذریعہ بنے۔',
      action: 'شامل ہوں', secondary: 'ہمارا کام جانیں', note: 'مقامی لوگ، مشترکہ مقصد۔',
    },
    about: {
      title: 'لوگوں سے بنتا ہے معاشرہ',
      paragraphs: [
        'ہر محلے میں ایسے لوگ ہوتے ہیں جو دوسروں کی مدد کرنا چاہتے ہیں۔ برانچ آفس مقامی رضاکاروں، شاخوں اور مرکزی دفتر کو ایک دوسرے سے جوڑتا ہے۔',
        'شاخیں مقامی کام کو منظم کرتی ہیں۔ رضاکار اپنا وقت اور ہنر دیتے ہیں۔ مرکزی دفتر اس نیٹ ورک کی رہنمائی کرتا ہے اور کام کو جواب دہ رکھتا ہے۔',
      ],
      closing: 'مقامی تعلق، مشترکہ کوشش۔',
    },
    programs: {
      title: 'اپنے وقت کو بامقصد بنائیں',
      intro: 'اپنا وقت دیں، ہنر بانٹیں یا مقامی ٹیم کی مدد کریں۔ آغاز کے لیے ہماری شاخوں کے پروگرام اور تقریبات دیکھیں۔',
      items: [
        { title: 'اپنا وقت دیں', body: 'مقامی سرگرمیوں میں رضاکاروں کے ساتھ کام کریں۔ مواقع شائع ہونے پر ضرورت اور شرکت کا طریقہ بتایا جائے گا۔' },
        { title: 'اپنا ہنر بانٹیں', body: 'اپنا تجربہ، خیالات یا انتظامی صلاحیت مقامی ٹیم کے ساتھ بانٹیں۔ مناسب موقع وہ ہے جہاں آپ کی صلاحیت کام آ سکے۔' },
        { title: 'مقامی کام میں مدد دیں', body: 'کسی شاخ کی سرگرمیوں کو منظم کرنے اور کام آگے بڑھانے میں مدد کریں۔ یہ ویب سائٹ آن لائن ادائیگیاں وصول نہیں کرتی۔' },
      ],
    },
    branches: {
      title: 'اپنے لوگوں سے جڑیں',
      body: 'ہماری شاخیں مقامی خدمت کا مرکز ہیں۔ یہ آس پاس کے لوگوں کو جوڑتی، رضاکاروں کو منظم کرتی اور مرکزی دفتر کو پیش رفت سے آگاہ رکھتی ہیں۔',
      empty: 'شاخوں کی فہرست شائع ہونے پر مقامات اور مقامی رابطوں کی معلومات یہاں دستیاب ہوں گی۔',
      action: 'شرکت کا طریقہ',
    },
    events: {
      title: 'مل جل کر وقت گزاریں',
      body: 'مقامی کام کرنے والے لوگوں سے ملیں۔ آنے والی سرگرمیوں اور شرکت کے مواقع کی تفصیل یہاں ملے گی۔',
      emptyTitle: 'ابھی کوئی تقریب شائع نہیں ہوئی', empty: 'نئی تقریبات کے اعلان کے ساتھ تاریخ، مقام اور شرکت کی تفصیل یہاں دی جائے گی۔',
    },
    join: {
      title: 'آپ کا وقت قیمتی ہے',
      body: 'پہلا قدم لینے کے لیے عملے کا اکاؤنٹ ضروری نہیں۔ شاخ منتخب کریں، اپنی دلچسپی بتائیں اور دستیابی سے آگاہ کریں۔',
      steps: [
        { title: 'اپنی شاخ تلاش کریں', body: 'شائع شدہ معلومات دیکھیں اور اپنے قریب کی ٹیم تلاش کریں۔' },
        { title: 'اپنا تعارف کروائیں', body: 'اپنی دلچسپی اور معلومات کے ساتھ رضاکارانہ درخواست مکمل کریں۔' },
        { title: 'اپنی ٹیم سے ملیں', body: 'ایچ آر ٹیم درخواستوں کا جائزہ لے گی اور قبول ہونے والے رضاکاروں کی رہنمائی کرے گی۔' },
      ],
      notice: 'رضاکارانہ درخواستیں ابھی نہیں کھلیں۔ نئے مواقع کے لیے دوبارہ تشریف لائیں۔', staffPrompt: 'کیا آپ پہلے سے عملے کا حصہ ہیں؟',
    },
    contact: {
      title: 'رابطے میں رہیں', body: 'مقامی سوالات کے لیے گفتگو ضروری ہے۔ کسی شاخ، پروگرام یا اپنے خیال کے بارے میں پیغام بھیجیں۔',
      empty: 'رابطے کی معلومات ابھی شائع نہیں ہوئیں۔', explore: 'مزید جانیں', staffTitle: 'ہمارے عملے کے لیے',
      staffBody: 'اپنے سپر ایڈمن کی فراہم کردہ معلومات سے اپنے کام کی جگہ پر لاگ اِن کریں۔',
    },
    footer: { note: 'لوگ، پروگرام، ترقی۔', top: 'اوپر جائیں' },
  },
};
