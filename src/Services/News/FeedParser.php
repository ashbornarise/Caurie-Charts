<?php

namespace Cauri\Services\News;

/** Lit un flux RSS 2.0 ou Atom et en extrait des articles normalisés. */
final class FeedParser
{
    private const MEDIA = 'http://search.yahoo.com/mrss/';
    private const CONTENT = 'http://purl.org/rss/1.0/modules/content/';

    /** @return list<array{guid:string,title:string,url:string,summary:string,published_at:?string,image:?string}> */
    public static function parse(string $xml): array
    {
        $previous = libxml_use_internal_errors(true);
        $doc = simplexml_load_string($xml, \SimpleXMLElement::class, LIBXML_NOCDATA | LIBXML_NONET);
        libxml_clear_errors();
        libxml_use_internal_errors($previous);
        if ($doc === false) {
            return [];
        }
        $items = [];
        if (isset($doc->channel->item)) {
            foreach ($doc->channel->item as $item) {
                $items[] = self::rssItem($item);
            }
        } elseif ($doc->getName() === 'feed') {
            foreach ($doc->entry as $entry) {
                $items[] = self::atomEntry($entry);
            }
        }
        return array_values(array_filter($items, fn ($i) => $i['title'] !== '' && self::isHttp($i['url'])));
    }

    private static function rssItem(\SimpleXMLElement $item): array
    {
        $url = trim((string) $item->link);
        $content = (string) ($item->children(self::CONTENT)->encoded ?? '');
        $description = (string) $item->description;
        return [
            'guid'         => trim((string) $item->guid) ?: $url,
            'title'        => self::text((string) $item->title),
            'url'          => $url,
            'summary'      => self::summary($description !== '' ? $description : $content),
            'published_at' => self::date((string) $item->pubDate),
            'image'        => self::image($item, $description . $content),
        ];
    }

    private static function atomEntry(\SimpleXMLElement $entry): array
    {
        $url = '';
        foreach ($entry->link as $link) {
            if ((string) $link['rel'] === '' || (string) $link['rel'] === 'alternate') {
                $url = (string) $link['href'];
                break;
            }
        }
        $html = (string) $entry->summary . (string) $entry->content;
        return [
            'guid'         => trim((string) $entry->id) ?: $url,
            'title'        => self::text((string) $entry->title),
            'url'          => $url,
            'summary'      => self::summary($html),
            'published_at' => self::date((string) ($entry->published ?: $entry->updated)),
            'image'        => self::image($entry, $html),
        ];
    }

    /** Image de l'article : media:content, media:thumbnail, enclosure image, puis première <img> du contenu. */
    private static function image(\SimpleXMLElement $item, string $html): ?string
    {
        $media = $item->children(self::MEDIA);
        foreach ($media->content ?? [] as $c) {
            $type = (string) $c->attributes()->type;
            $medium = (string) $c->attributes()->medium;
            if ($medium === 'image' || str_starts_with($type, 'image/') || ($type === '' && $medium === '')) {
                $url = (string) $c->attributes()->url;
                if (self::isHttp($url)) {
                    return $url;
                }
            }
        }
        foreach ($media->thumbnail ?? [] as $t) {
            $url = (string) $t->attributes()->url;
            if (self::isHttp($url)) {
                return $url;
            }
        }
        foreach ($item->enclosure ?? [] as $e) {
            if (str_starts_with((string) $e['type'], 'image/') && self::isHttp((string) $e['url'])) {
                return (string) $e['url'];
            }
        }
        if (preg_match('/<img[^>]+src=["\']([^"\']+)["\']/i', $html, $m) && self::isHttp(html_entity_decode($m[1]))) {
            return html_entity_decode($m[1]);
        }
        return null;
    }

    /** og:image d'une page d'article (quand le flux ne fournit pas d'image). */
    public static function ogImage(string $html): ?string
    {
        foreach (['og:image', 'twitter:image'] as $prop) {
            if (preg_match('/<meta[^>]+(?:property|name)=["\']' . preg_quote($prop, '/') . '["\'][^>]*content=["\']([^"\']+)["\']/i', $html, $m)
                || preg_match('/<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']' . preg_quote($prop, '/') . '["\']/i', $html, $m)) {
                $url = html_entity_decode($m[1]);
                if (self::isHttp($url)) {
                    return $url;
                }
            }
        }
        return null;
    }

    public static function isHttp(string $url): bool
    {
        return (bool) preg_match('#^https?://[^\s/$.?\#][^\s]*$#i', $url);
    }

    private static function text(string $value): string
    {
        return trim(preg_replace('/\s+/u', ' ', html_entity_decode(strip_tags($value), ENT_QUOTES | ENT_HTML5, 'UTF-8')));
    }

    private static function summary(string $html): string
    {
        // Les flux WordPress terminent souvent par « L'article X est apparu en premier sur Y ».
        $html = preg_replace('#<p>\s*(L[’\']article|The post)\b.*?</p>#isu', '', $html);
        $text = self::text($html);
        $text = preg_replace('/\s*(\[(…|\.\.\.|&#8230;)\]|Lire la suite.*|Read more.*)$/iu', '…', $text);
        if (mb_strlen($text) > 260) {
            $text = rtrim(mb_substr($text, 0, 257), " ,.;:-") . '…';
        }
        return $text;
    }

    private static function date(string $value): ?string
    {
        $ts = $value !== '' ? strtotime($value) : false;
        return $ts ? gmdate('Y-m-d H:i:s', $ts) : null;
    }
}
