from diffkemp_htmlgen.htmlgen import Diff


def test_diff():
    diff_str = """    *************** try_to_wake_up(struct task_struct *p, unsigned int state, int wake_flags)
    *** 1665,1666 ***
    --- 1725,1748 ---
      
    +   /*
    +    * Ensure we load p->on_rq _after_ p->state, otherwise it would
    +    * be possible to, falsely, observe p->on_rq == 0 and get stuck
    +    * in smp_cond_load_acquire() below.
    +    *
    +    * sched_ttwu_pending()                 try_to_wake_up()
    +    *   [S] p->on_rq = 1;                  [L] P->state
    +    *       UNLOCK rq->lock  -----.
    +    *                              \\
    +    *                               +---   RMB
    +    * schedule()                   /
    +    *       LOCK rq->lock    -----'
    +    *       UNLOCK rq->lock
    +    *
    +    * [task p]
    +    *   [S] p->state = UNINTERRUPTIBLE     [L] p->on_rq
    +    *
    +    * Pairs with the UNLOCK+LOCK on rq->lock from the
    +    * last wakeup of our task and the schedule that got our task
    +    * current.
    +    */
    +   smp_rmb();
        if (p->on_rq && ttwu_remote(p, wake_flags))
    *************** try_to_wake_up(struct task_struct *p, unsigned int state, int wake_flags)
    *** 1670,1671 ***
    --- 1752,1772 ---
        /*
    +    * Ensure we load p->on_cpu _after_ p->on_rq, otherwise it would be
    +    * possible to, falsely, observe p->on_cpu == 0.
    +    *
    +    * One must be running (->on_cpu == 1) in order to remove oneself
    +    * from the runqueue.
    +    *
    +    *  [S] ->on_cpu = 1;   [L] ->on_rq
    +    *      UNLOCK rq->lock
    +    *                      RMB
    +    *      LOCK   rq->lock
    +    *  [S] ->on_rq = 0;    [L] ->on_cpu
    +    *
    +    * Pairs with the full barrier implied in the UNLOCK+LOCK on rq->lock
    +    * from the consecutive calls to schedule(); the first switching to our
    +    * task, the second putting it to sleep.
    +    */
    +   smp_rmb();
    + 
    +   /*
         * If the owning (remote) cpu is still in the middle of schedule() with"""
    diff = Diff(diff_str)

    assert len(diff.fragments) == 2

    fragment = diff.fragments[0]
    assert fragment.start_line_left == 1665
    assert fragment.start_line_right == 1725
    assert fragment.function_name == ("try_to_wake_up(struct task_struct *p, u"
                                      "nsigned int state, int wake_flags)")
    assert len(fragment.lines_left) == 0
    assert len(fragment.lines_right) == 24

    fragment = diff.fragments[1]
    assert fragment.start_line_left == 1670
    assert fragment.start_line_right == 1752
    assert fragment.function_name == ("try_to_wake_up(struct task_struct *p, u"
                                      "nsigned int state, int wake_flags)")
    assert len(fragment.lines_left) == 0
    assert len(fragment.lines_right) == 21
