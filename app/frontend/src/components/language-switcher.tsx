import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { useTranslation } from 'react-i18next';
import { Languages } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useState } from 'react';

const languages = [
  { code: 'en', label: 'English', nativeLabel: 'English' },
  { code: 'zh-CN', label: '简体中文', nativeLabel: '简体中文' },
  { code: 'zh-TW', label: '繁體中文', nativeLabel: '繁體中文' },
];

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const [open, setOpen] = useState(false);

  const handleLanguageChange = (langCode: string) => {
    i18n.changeLanguage(langCode);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
          aria-label={t('language.switch')}
          title={t('language.switch')}
        >
          <Languages size={16} />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-48 p-1">
        <div className="flex flex-col">
          {languages.map((lang) => (
            <button
              key={lang.code}
              onClick={() => handleLanguageChange(lang.code)}
              className={cn(
                "flex items-center justify-between w-full px-3 py-2 text-sm rounded-sm transition-colors",
                "hover:bg-accent hover:text-accent-foreground",
                i18n.language === lang.code && "bg-accent text-accent-foreground"
              )}
            >
              <span>{lang.nativeLabel}</span>
              {i18n.language === lang.code && (
                <span className="text-xs">✓</span>
              )}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

