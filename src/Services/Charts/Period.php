<?php

namespace Cauri\Services\Charts;

/**
 * Périodes de suivi. Semaine : lundi 00 h 00 au dimanche 23 h 59, heure de Lomé.
 * Une semaine appartient au mois (et à l'année) de son dimanche.
 */
final class Period
{
    private function __construct(
        public readonly string $type,
        public readonly string $key,
        public readonly string $start,
        public readonly string $end,
    ) {
    }

    public static function weekOf(string $date): Period
    {
        $ts = strtotime($date);
        $monday = strtotime('-' . ((int) date('N', $ts) - 1) . ' days', $ts);
        $sunday = strtotime('+6 days', $monday);
        return new Period('week', date('o-\WW', $monday), date('Y-m-d', $monday), date('Y-m-d', $sunday));
    }

    /** Dernière semaine terminée avant $today (le lundi, c'est la semaine d'hier). */
    public static function lastCompletedWeek(string $today): Period
    {
        return self::weekOf(date('Y-m-d', strtotime($today . ' -7 days')));
    }

    public static function fromKey(string $type, string $key): Period
    {
        return match ($type) {
            'week'  => self::weekFromKey($key),
            'month' => self::month($key),
            'year'  => self::year($key),
            default => throw new \InvalidArgumentException("Période inconnue : $type"),
        };
    }

    public static function weekFromKey(string $key): Period
    {
        if (!preg_match('/^(\d{4})-W(\d{2})$/', $key, $m)) {
            throw new \InvalidArgumentException("Semaine invalide : $key");
        }
        $dt = (new \DateTimeImmutable())->setISODate((int) $m[1], (int) $m[2], 1);
        return self::weekOf($dt->format('Y-m-d'));
    }

    /** Mois = semaines dont le dimanche tombe dans le mois. */
    public static function month(string $key): Period
    {
        if (!preg_match('/^\d{4}-\d{2}$/', $key)) {
            throw new \InvalidArgumentException("Mois invalide : $key");
        }
        $first = strtotime($key . '-01');
        $last = strtotime(date('Y-m-t', $first));
        $firstSunday = strtotime('+' . ((7 - (int) date('N', $first)) % 7) . ' days', $first);
        $lastSunday = strtotime('-' . ((int) date('N', $last) % 7) . ' days', $last);
        return new Period('month', $key, date('Y-m-d', strtotime('-6 days', $firstSunday)), date('Y-m-d', $lastSunday));
    }

    public static function year(string $key): Period
    {
        $jan = self::month($key . '-01');
        $dec = self::month($key . '-12');
        return new Period('year', $key, $jan->start, $dec->end);
    }

    /** Lundis des semaines comprises dans la période. */
    public function weekStarts(): array
    {
        $out = [];
        for ($ts = strtotime($this->start); $ts <= strtotime($this->end); $ts = strtotime('+7 days', $ts)) {
            $out[] = date('Y-m-d', $ts);
        }
        return $out;
    }

    public function previous(): Period
    {
        return match ($this->type) {
            'week'  => self::weekOf(date('Y-m-d', strtotime($this->start . ' -7 days'))),
            'month' => self::month(date('Y-m', strtotime($this->key . '-01 -1 month'))),
            'year'  => self::year((string) ((int) $this->key - 1)),
        };
    }

    public function monthKey(): string
    {
        return substr($this->end, 0, 7);
    }
}
