STDLIB = '''
(defn inc (x) (+ x 1))
(defn dec (x) (- x 1))
(defn first (lst) (nth lst 0))
(defn second (lst) (nth lst 1))
(defn last (lst) (nth lst -1))
(defn zero? (x) (= x 0))
(defn empty? (lst) (= 0 (len lst)))
(defn cons (x lst) (+ (list x) lst))
(defn append (lst x) (do ((. append lst) x) lst))
(defn extend (lst1 lst2) (do ((. extend lst1) lst2) lst1))

(defn rest (lst)
    (do
        (defn aux (i result)
            (if (= i (len lst)) result
            (if (zero? i) (aux (inc i) result)
            (aux (inc i) (append result (nth lst i))))))
        (aux 0 (list))))

(defn skip (count lst)
    (do
        (defn aux (i result)
            (if (= i (len lst)) result
            (if (< i count) (aux (inc i) result)
            (aux (inc i) (append result (nth lst i))))))
        (aux 0 (list))))

(defn filter (function lst)
    (do
        (defn aux (i result)
            (if (= i (len lst)) result
            (if (function (nth lst i))
                (aux (inc i) (append result (nth lst i)))
                (aux (inc i) result))))
        (aux 0 (list))))

(defn map (function lst)
    (do
        (defn aux (l)
            (if (empty? l)
                (list)
                (cons (function (first l)) (aux (rest l)))))
        (aux lst)))

(defn curry (function & args1)
    (defn _ ( & args2)
        (function & (+ args1 args2))))

(defn zip (& lists)
    (let (length (min (map (# len %0) lists)))
        (do (defn aux (i result)
            (if (>= i length) result
                (do
                    (append result (map (# nth %0 i) lists))
                    (aux (inc i) result))))
            (aux 0 (list)))))

(defn flatten (lst) 
    (do 
        (defn aux (i result)
            (if (>= i (len lst))
                result
                (let (item (nth lst i))
                    (if (is_list item)
                        (aux (inc i) (extend result (flatten item)))
                        (aux (inc i) (append result item))))))
        (aux 0 (list))))

(defn reduce (function initial & lst)
    (do
        (defn aux (i result)
            (if (= i (len lst))
                result
                (aux (inc i) (function result (nth lst i)))))
        (aux 0 initial)))

(defn concat (& lists)
    (reduce (# extend %0 %1) (list) & lists))

(defmacro when (cond & body)
    (list 'if cond (cons 'do body) None))

(defmacro unless (cond body)
    (list 'if (list 'not cond) body None))

(defmacro letfn (function expression)
    (let (fname (first function)
          fparams (second function)
          fbody (last function)
          anon (map (# list '$ (+ "%" (str %0))) (range (len fparams))))

        (list 'let (list fname (list '# 'let (concat & (zip fparams anon)) fbody))
            expression)))
'''
