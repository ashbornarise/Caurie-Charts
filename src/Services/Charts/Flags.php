<?php

namespace Cauri\Services\Charts;

/** Codes de signalement. Les signalements "bloquants" retiennent la publication. */
final class Flags
{
    // Bloquants : validation ou exclusion par un admin avant publication
    public const SPIKE = 'spike';
    public const DECLARATION_MISMATCH = 'declaration_mismatch';
    public const YOUTUBE_RATIO = 'youtube_ratio';

    // Informatifs
    public const NEGATIVE_DELTA = 'negative_delta';
    public const DECLARATION_UNCORROBORATED = 'declaration_uncorroborated';
    public const DIVERSITY_CAPPED = 'diversity_capped';
    public const DIVERSITY_FALLBACK = 'diversity_fallback';

    public const BLOCKING = [self::SPIKE, self::DECLARATION_MISMATCH, self::YOUTUBE_RATIO];

    public static function hasBlocking(array $flags): bool
    {
        return (bool) array_intersect($flags, self::BLOCKING);
    }
}
